"""POST/GET/DELETE /analytics/projections, GET /analytics/algorithms,
POST /analytics/run, POST /analytics/persist -- full analytics engine API
surface (PLAN: plans/analytical-engine.md Slices 1-2, 8).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from analytics.projection import EmptyGraphError, NamedProjection
from analytics.registry import default_registry
from analytics.result import AlgorithmResult
from analytics.store import Neo4jGraphStore
from app.dependencies import get_neo4j
from app.schemas import ApiModel
from db.neo4j_client import Neo4jClient

router = APIRouter(tags=["analytics"])


class CreateProjectionRequest(ApiModel):
    name: str | None = None


class ProjectionResponse(ApiModel):
    name: str
    graph_id: str
    node_count: int
    edge_count: int


class ProjectionsListResponse(ApiModel):
    projections: list[ProjectionResponse]


class RunAlgorithmRequest(ApiModel):
    projection: str
    algorithm: str


class AlgorithmResultResponse(ApiModel):
    algorithm: str
    projection: str
    node_scores: dict[str, float]
    suggested_chart: str | None = None


class AlgorithmInfo(ApiModel):
    name: str
    category: str
    params: dict[str, object]


class AlgorithmsListResponse(ApiModel):
    algorithms: list[AlgorithmInfo]


class PersistRequest(ApiModel):
    projection: str
    algorithm: str
    property_name: str


class PersistResponse(ApiModel):
    projection: str
    algorithm: str
    property_name: str
    node_count: int


def _to_projection_response(projection: NamedProjection) -> ProjectionResponse:
    return ProjectionResponse(
        name=projection.name,
        graph_id=projection.graph_id,
        node_count=projection.graph.number_of_nodes(),
        edge_count=projection.graph.number_of_edges(),
    )


def _get_projection_or_404(name: str) -> NamedProjection:
    projection = NamedProjection.get(name)
    if projection is None:
        raise HTTPException(status_code=404, detail=f"Unknown projection: {name}")
    return projection


def _get_algorithm_spec_or_400(name: str):
    spec = default_registry.get(name)
    if spec is None:
        raise HTTPException(status_code=400, detail=f"Unknown algorithm: {name}")
    return spec


@router.post("/analytics/projections/{graph_id}", response_model=ProjectionResponse, response_model_by_alias=True)
def create_projection(graph_id: str, request: CreateProjectionRequest, neo4j: Neo4jClient = Depends(get_neo4j)) -> ProjectionResponse:
    name = request.name or graph_id
    try:
        projection = NamedProjection.create(neo4j, name=name, graph_id=graph_id)
    except EmptyGraphError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _to_projection_response(projection)


@router.get("/analytics/projections", response_model=ProjectionsListResponse, response_model_by_alias=True)
def list_projections() -> ProjectionsListResponse:
    return ProjectionsListResponse(projections=[_to_projection_response(p) for p in NamedProjection.list_all()])


@router.delete("/analytics/projections/{name}")
def drop_projection(name: str) -> dict[str, bool]:
    dropped = NamedProjection.drop(name)
    if not dropped:
        raise HTTPException(status_code=404, detail=f"Unknown projection: {name}")
    return {"dropped": True}


@router.get("/analytics/algorithms", response_model=AlgorithmsListResponse, response_model_by_alias=True)
def list_algorithms() -> AlgorithmsListResponse:
    return AlgorithmsListResponse(
        algorithms=[
            AlgorithmInfo(name=spec.name, category=spec.category, params=spec.params)
            for spec in default_registry.list()
        ]
    )


@router.post("/analytics/run", response_model=AlgorithmResultResponse, response_model_by_alias=True)
def run_algorithm(request: RunAlgorithmRequest) -> AlgorithmResultResponse:
    projection = _get_projection_or_404(request.projection)
    spec = _get_algorithm_spec_or_400(request.algorithm)

    scores = spec.func(projection.graph)
    return AlgorithmResultResponse(algorithm=spec.name, projection=request.projection, node_scores=scores, suggested_chart=spec.chart_type)


@router.post("/analytics/persist", response_model=PersistResponse, response_model_by_alias=True)
def persist_algorithm_result(request: PersistRequest, neo4j: Neo4jClient = Depends(get_neo4j)) -> PersistResponse:
    projection = _get_projection_or_404(request.projection)
    spec = _get_algorithm_spec_or_400(request.algorithm)

    scores = spec.func(projection.graph)
    result = AlgorithmResult(algorithm=spec.name, projection=projection, node_scores=scores)
    result.persist(Neo4jGraphStore(neo4j), request.property_name)

    return PersistResponse(
        projection=request.projection, algorithm=spec.name, property_name=request.property_name, node_count=len(scores)
    )
