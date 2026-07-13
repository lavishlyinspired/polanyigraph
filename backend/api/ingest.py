"""POST /ingest — real document text in, real extracted graph out.

No demo/seed data anywhere in this path: entities and relationships come only
from LLM extraction validated against the live ontology (see kg-extraction and
ontology-mapping SKILL.md).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.dependencies import get_embedder, get_graphdb, get_llm, get_neo4j
from app.schemas import ApiModel
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient
from llm.client import LLMClient
from llm.embedder import EmbeddingClient
from services import edgar_service, entity_resolution_service, memory_config_service
from services.ingest_service import ingest_text

router = APIRouter(tags=["ingest"])


class TextSource(ApiModel):
    type: str
    text: str | None = None
    # MVP_PLAN.md §7's optional EDGAR convenience source (type: "edgar").
    ticker: str | None = None
    form_type: str | None = None


class IngestRequest(ApiModel):
    graph_id: str
    source: TextSource


class NodeResponse(ApiModel):
    id: str
    label: str
    type: str
    activation: float | None = None
    derived: bool = False
    source_doc: str | None = None
    summary: str = ""


class EdgeResponse(ApiModel):
    id: str
    source: str
    target: str
    type: str
    weight: float = 1.0
    valid_at: str | None = None
    invalid_at: str | None = None
    produced_by_event_id: str | None = None


class IngestResponse(ApiModel):
    nodes: list[NodeResponse]
    edges: list[EdgeResponse]
    dropped: list[str]


@router.post("/ingest", response_model=IngestResponse, response_model_by_alias=True)
def ingest(
    request: IngestRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
    graphdb: GraphDBClient = Depends(get_graphdb),
    llm: LLMClient = Depends(get_llm),
    settings: Settings = Depends(get_settings),
    embedder: EmbeddingClient = Depends(get_embedder),
) -> IngestResponse:
    if request.source.type == "text":
        if not request.source.text or not request.source.text.strip():
            raise HTTPException(status_code=400, detail="source.text must not be empty.")
        text = request.source.text
        source_doc = f"pasted-text:{request.graph_id}"
    elif request.source.type == "edgar":
        if not request.source.ticker or not request.source.form_type:
            raise HTTPException(status_code=400, detail="source.ticker and source.formType are required for type 'edgar'.")
        filing = edgar_service.fetch_filing(request.source.ticker, request.source.form_type)
        if filing is None:
            raise HTTPException(
                status_code=404,
                detail=f"No {request.source.form_type} filing found for ticker '{request.source.ticker}' on SEC EDGAR.",
            )
        text = filing.text
        source_doc = f"edgar:{filing.ticker}:{filing.form_type}:{filing.filed_at}"
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported source type '{request.source.type}'. Use 'text' or 'edgar'.")

    # Only index embeddings when the native memory backend is active
    # (GRAPHITI_INTEGRATION_PLAN.md §4 Option A) -- when "graphiti" is
    # selected instead, Graphiti owns its own embedding pipeline.
    active_embedder = embedder if memory_config_service.get_backend(neo4j) == "native" else None
    record, result = ingest_text(
        neo4j=neo4j,
        graphdb=graphdb,
        llm=llm,
        graph_id=request.graph_id,
        text=text,
        source_doc=source_doc,
        repository=settings.graphdb_repository,
        embedder=active_embedder,
    )

    return IngestResponse(
        nodes=[
            NodeResponse(id=n.id, label=n.label, type=n.type, activation=n.activation, derived=n.derived, source_doc=n.source_doc, summary=n.summary)
            for n in record.nodes
        ],
        edges=[
            EdgeResponse(
                id=e.id, source=e.source, target=e.target, type=e.type, weight=e.weight,
                valid_at=e.valid_at, invalid_at=e.invalid_at, produced_by_event_id=e.produced_by_event_id,
            )
            for e in record.edges
        ],
        dropped=result.dropped,
    )


class DuplicateCandidateResponse(ApiModel):
    id: str
    new_entity_id: str
    new_entity_label: str
    existing_entity_id: str
    existing_entity_label: str
    similarity: float
    status: str


class DuplicateCandidatesResponse(ApiModel):
    candidates: list[DuplicateCandidateResponse]


def _to_duplicate_response(c: dict) -> DuplicateCandidateResponse:
    return DuplicateCandidateResponse(
        id=c["id"], new_entity_id=c["newEntityId"], new_entity_label=c["newEntityLabel"],
        existing_entity_id=c["existingEntityId"], existing_entity_label=c["existingEntityLabel"],
        similarity=c["similarity"], status=c["status"],
    )


@router.get("/ingest/{graph_id}/duplicates", response_model=DuplicateCandidatesResponse, response_model_by_alias=True)
def get_duplicate_candidates(
    graph_id: str, status: str = "pending", neo4j: Neo4jClient = Depends(get_neo4j),
) -> DuplicateCandidatesResponse:
    candidates = entity_resolution_service.list_candidates(neo4j, graph_id=graph_id, status=status)
    return DuplicateCandidatesResponse(candidates=[_to_duplicate_response(c) for c in candidates])


@router.post("/ingest/duplicates/{candidate_id}/confirm")
def confirm_duplicate_candidate(candidate_id: str, neo4j: Neo4jClient = Depends(get_neo4j)) -> dict[str, bool]:
    entity_resolution_service.confirm_duplicate(neo4j, candidate_id)
    return {"confirmed": True}


@router.post("/ingest/duplicates/{candidate_id}/reject")
def reject_duplicate_candidate(candidate_id: str, neo4j: Neo4jClient = Depends(get_neo4j)) -> dict[str, bool]:
    entity_resolution_service.reject_duplicate(neo4j, candidate_id)
    return {"rejected": True}
