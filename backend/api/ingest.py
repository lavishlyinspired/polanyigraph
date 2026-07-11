"""POST /ingest — real document text in, real extracted graph out.

No demo/seed data anywhere in this path: entities and relationships come only
from LLM extraction validated against the live ontology (see kg-extraction and
ontology-mapping SKILL.md).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.dependencies import get_graphdb, get_llm, get_neo4j
from app.schemas import ApiModel
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient
from llm.client import LLMClient
from services.ingest_service import ingest_text

router = APIRouter(tags=["ingest"])


class TextSource(ApiModel):
    type: str
    text: str


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


class EdgeResponse(ApiModel):
    id: str
    source: str
    target: str
    type: str
    weight: float = 1.0


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
) -> IngestResponse:
    if request.source.type != "text":
        raise HTTPException(status_code=400, detail=f"Unsupported source type '{request.source.type}'. Only 'text' is supported in the MVP.")
    if not request.source.text.strip():
        raise HTTPException(status_code=400, detail="source.text must not be empty.")

    record, result = ingest_text(
        neo4j=neo4j,
        graphdb=graphdb,
        llm=llm,
        graph_id=request.graph_id,
        text=request.source.text,
        source_doc=f"pasted-text:{request.graph_id}",
        repository=settings.graphdb_repository,
    )

    return IngestResponse(
        nodes=[
            NodeResponse(id=n.id, label=n.label, type=n.type, activation=n.activation, derived=n.derived, source_doc=n.source_doc)
            for n in record.nodes
        ],
        edges=[EdgeResponse(id=e.id, source=e.source, target=e.target, type=e.type, weight=e.weight) for e in record.edges],
        dropped=result.dropped,
    )
