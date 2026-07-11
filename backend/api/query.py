"""POST /query/{graph_id} — structured triple query, path-finding, and triple store."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_neo4j
from app.schemas import ApiModel
from db.neo4j_client import Neo4jClient
from services import graph_service
from services.query_engine import execute_query
from services.path_engine import find_path

router = APIRouter(tags=["query"])


# ── Query ────────────────────────────────────────────────────────────────────

class QueryRequest(ApiModel):
    query: str


class ResultRowResponse(ApiModel):
    subject: str
    predicate: str
    object: str
    derived: bool
    confidence: float


class QueryResponse(ApiModel):
    query: str
    results: list[ResultRowResponse]
    error: str | None = None


@router.post("/query/{graph_id}", response_model=QueryResponse, response_model_by_alias=True)
def query_graph(graph_id: str, request: QueryRequest, neo4j: Neo4jClient = Depends(get_neo4j)) -> QueryResponse:
    triples = graph_service.load_triples(neo4j, graph_id)
    result = execute_query(request.query, triples)
    return QueryResponse(
        query=result.query,
        results=[
            ResultRowResponse(subject=r.subject, predicate=r.predicate, object=r.object, derived=r.derived, confidence=r.confidence)
            for r in result.results
        ],
        error=result.error,
    )


# ── Path-finding ─────────────────────────────────────────────────────────────

class PathRequest(ApiModel):
    source: str
    target: str


class PathEdgeResponse(ApiModel):
    source: str
    target: str
    label: str


class PathResponse(ApiModel):
    found: bool
    path: list[str]
    edges: list[PathEdgeResponse]
    proof: str
    error: str | None = None


@router.post("/query/{graph_id}/path", response_model=PathResponse, response_model_by_alias=True)
def find_path_endpoint(
    graph_id: str,
    request: PathRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> PathResponse:
    record = graph_service.get_graph(neo4j, graph_id)
    result = find_path(request.source, request.target, record.nodes, record.edges)
    return PathResponse(
        found=result.found,
        path=result.path,
        edges=[PathEdgeResponse(source=e.source, target=e.target, label=e.label) for e in result.edges],
        proof=result.proof,
        error=result.error,
    )


# ── Triple store ─────────────────────────────────────────────────────────────

class TripleResponse(ApiModel):
    subject: str
    predicate: str
    object: str
    derived: bool
    confidence: float


class TriplesResponse(ApiModel):
    triples: list[TripleResponse]
    total: int


@router.get("/query/{graph_id}/triples", response_model=TriplesResponse, response_model_by_alias=True)
def get_triples(
    graph_id: str,
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> TriplesResponse:
    triples = graph_service.load_triples(neo4j, graph_id)
    return TriplesResponse(
        triples=[
            TripleResponse(subject=t.subject, predicate=t.predicate, object=t.object, derived=t.derived, confidence=t.confidence)
            for t in triples
        ],
        total=len(triples),
    )
