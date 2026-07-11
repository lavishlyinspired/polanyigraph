"""POST /reason/{graph_id} — run the neurosymbolic loop (PLAN.md §8.4) and persist results."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.dependencies import get_graphdb, get_neo4j
from app.schemas import ApiModel
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient
from services import graph_service, reasoning_service

router = APIRouter(tags=["reason"])


class ReasonRequest(ApiModel):
    source_id: str | None = None


class ProofStepResponse(ApiModel):
    rule_name: str
    edge_type: str
    source_label: str
    target_label: str
    premise_activation: float
    iteration: int
    type_resolution: str | None = None


class DerivedFactResponse(ApiModel):
    id: str
    fact: str
    confidence: float
    iteration: int
    source_id: str
    target_id: str
    rule_name: str
    proof_path: list[ProofStepResponse] = []
    fed_back: bool = False


class ReasonResponse(ApiModel):
    activation: dict[str, float]
    facts: list[DerivedFactResponse]
    iterations: int
    converged_by: str


class TraceEntryResponse(ApiModel):
    rule_name: str
    edge_type: str
    source_label: str
    target_label: str
    source_activation: float
    threshold: float
    fired: bool
    iteration: int
    skip_reason: str | None = None
    fact_id: str | None = None


class SpreadResponse(ApiModel):
    activation: dict[str, float]


class InferResponse(ApiModel):
    facts: list[DerivedFactResponse]
    trace: list[TraceEntryResponse]


class FeedbackResponse(ApiModel):
    activation: dict[str, float]


class FactsListResponse(ApiModel):
    facts: list[DerivedFactResponse]


def _to_derived_fact_response(f, *, fed_back: bool = False) -> DerivedFactResponse:
    return DerivedFactResponse(
        id=f.id, fact=f.fact, confidence=f.confidence, iteration=f.iteration,
        source_id=f.source_id, target_id=f.target_id, rule_name=f.rule_name,
        proof_path=[
            ProofStepResponse(
                rule_name=step.rule_name, edge_type=step.edge_type,
                source_label=step.source_label, target_label=step.target_label,
                premise_activation=step.premise_activation, iteration=step.iteration,
                type_resolution=step.type_resolution,
            )
            for step in f.proof_path
        ],
        fed_back=fed_back,
    )


@router.post("/reason/{graph_id}", response_model=ReasonResponse, response_model_by_alias=True)
def reason_over_graph(
    graph_id: str,
    request: ReasonRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
    graphdb: GraphDBClient = Depends(get_graphdb),
    settings: Settings = Depends(get_settings),
) -> ReasonResponse:
    try:
        result = reasoning_service.run_reasoning(
            neo4j, graphdb, settings, graph_id=graph_id, source_id=request.source_id,
        )
    except reasoning_service.EmptyGraphError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except reasoning_service.UnknownSourceError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return ReasonResponse(
        activation=result.activation,
        facts=[_to_derived_fact_response(f) for f in result.facts],
        iterations=result.iterations,
        converged_by=result.converged_by,
    )


# --- Manual step-by-step mode (Reason tab prototype parity) -----------------

@router.post("/reason/{graph_id}/spread", response_model=SpreadResponse, response_model_by_alias=True)
def spread_activation(
    graph_id: str,
    request: ReasonRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
    settings: Settings = Depends(get_settings),
) -> SpreadResponse:
    try:
        activation = reasoning_service.spread_activation_step(
            neo4j, graph_id, request.source_id, decay=settings.reason_decay,
        )
    except reasoning_service.EmptyGraphError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except reasoning_service.UnknownSourceError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return SpreadResponse(activation=activation)


@router.post("/reason/{graph_id}/infer", response_model=InferResponse, response_model_by_alias=True)
def run_inference(
    graph_id: str,
    neo4j: Neo4jClient = Depends(get_neo4j),
    graphdb: GraphDBClient = Depends(get_graphdb),
    settings: Settings = Depends(get_settings),
) -> InferResponse:
    try:
        new_facts, trace = reasoning_service.run_inference_step(neo4j, graphdb, settings, graph_id)
    except reasoning_service.EmptyGraphError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return InferResponse(
        facts=[_to_derived_fact_response(f) for f in new_facts],
        trace=[
            TraceEntryResponse(
                rule_name=t.rule_name, edge_type=t.edge_type,
                source_label=t.source_label, target_label=t.target_label,
                source_activation=t.source_activation, threshold=t.threshold,
                fired=t.fired, iteration=t.iteration, skip_reason=t.skip_reason, fact_id=t.fact_id,
            )
            for t in trace
        ],
    )


@router.post("/reason/{graph_id}/feedback", response_model=FeedbackResponse, response_model_by_alias=True)
def feed_back(
    graph_id: str,
    neo4j: Neo4jClient = Depends(get_neo4j),
    settings: Settings = Depends(get_settings),
) -> FeedbackResponse:
    activation = reasoning_service.feed_back_step(neo4j, graph_id, feedback_gain=settings.reason_feedback_gain)
    return FeedbackResponse(activation=activation)


@router.get("/reason/{graph_id}/facts", response_model=FactsListResponse, response_model_by_alias=True)
def get_facts(graph_id: str, neo4j: Neo4jClient = Depends(get_neo4j)) -> FactsListResponse:
    full = graph_service.get_derived_facts_full(neo4j, graph_id)
    return FactsListResponse(facts=[_to_derived_fact_response(f, fed_back=f.fed_back) for f in full])


@router.post("/reason/{graph_id}/clear-activation")
def clear_activation(graph_id: str, neo4j: Neo4jClient = Depends(get_neo4j)) -> dict:
    graph_service.clear_activation(neo4j, graph_id)
    return {"cleared": True}


@router.post("/reason/{graph_id}/clear-facts")
def clear_facts(graph_id: str, neo4j: Neo4jClient = Depends(get_neo4j)) -> dict:
    graph_service.clear_derived_facts(neo4j, graph_id)
    return {"cleared": True}
