"""POST /enrich/{graph_id} — Polanyi enrichment (PLAN.md §19). Runs all 11
heuristics together (§19.2: they ship together, not filtered by domain).
Human-in-the-loop: results are pending until a caller explicitly approves or
rejects them (§7.3)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_llm, get_neo4j
from app.schemas import ApiModel
from db.neo4j_client import Neo4jClient
from llm.client import LLMClient
from services import enrichment_service, graph_service

router = APIRouter(tags=["enrich"])


class EnrichRequest(ApiModel):
    text: str


class ImplicitFactResponse(ApiModel):
    id: str
    heuristic_type: str
    text: str
    confidence: float
    status: str
    anchor_entity_ids: list[str]


class ImplicitFactListResponse(ApiModel):
    facts: list[ImplicitFactResponse]


def _to_response(record: enrichment_service.ImplicitFactRecord) -> ImplicitFactResponse:
    return ImplicitFactResponse(
        id=record.id, heuristic_type=record.heuristic_type, text=record.text,
        confidence=record.confidence, status=record.status,
        anchor_entity_ids=list(record.anchor_entity_ids),
    )


@router.post("/enrich/{graph_id}", response_model=ImplicitFactListResponse, response_model_by_alias=True)
def enrich(
    graph_id: str,
    request: EnrichRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
    llm: LLMClient = Depends(get_llm),
) -> ImplicitFactListResponse:
    record = graph_service.get_graph(neo4j, graph_id)
    candidates = enrichment_service.run_all_heuristics(llm, nodes=record.nodes, edges=record.edges, source_text=request.text)
    ids = enrichment_service.save_pending_facts(neo4j, graph_id=graph_id, source_doc=request.text, candidates=candidates)

    pending = enrichment_service.list_pending_facts(neo4j, graph_id)
    created = [f for f in pending if f.id in set(ids)]
    return ImplicitFactListResponse(facts=[_to_response(f) for f in created])


@router.get("/enrich/{graph_id}/pending", response_model=ImplicitFactListResponse, response_model_by_alias=True)
def list_pending(graph_id: str, neo4j: Neo4jClient = Depends(get_neo4j)) -> ImplicitFactListResponse:
    facts = enrichment_service.list_pending_facts(neo4j, graph_id)
    return ImplicitFactListResponse(facts=[_to_response(f) for f in facts])


@router.get("/enrich/{graph_id}/approved", response_model=ImplicitFactListResponse, response_model_by_alias=True)
def list_approved(graph_id: str, neo4j: Neo4jClient = Depends(get_neo4j)) -> ImplicitFactListResponse:
    facts = enrichment_service.list_approved_facts(neo4j, graph_id)
    return ImplicitFactListResponse(facts=[_to_response(f) for f in facts])


@router.post("/enrich/{graph_id}/{fact_id}/approve", response_model=ImplicitFactListResponse, response_model_by_alias=True)
def approve(graph_id: str, fact_id: str, neo4j: Neo4jClient = Depends(get_neo4j)) -> ImplicitFactListResponse:
    enrichment_service.set_fact_status(neo4j, graph_id=graph_id, fact_id=fact_id, status="approved")
    return ImplicitFactListResponse(facts=[_to_response(f) for f in enrichment_service.list_approved_facts(neo4j, graph_id)])


@router.post("/enrich/{graph_id}/{fact_id}/reject", response_model=ImplicitFactListResponse, response_model_by_alias=True)
def reject(graph_id: str, fact_id: str, neo4j: Neo4jClient = Depends(get_neo4j)) -> ImplicitFactListResponse:
    enrichment_service.set_fact_status(neo4j, graph_id=graph_id, fact_id=fact_id, status="rejected")
    return ImplicitFactListResponse(facts=[])
