"""POST /reason/{graph_id} — run the neurosymbolic loop (PLAN.md §8.4) and persist results."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.dependencies import get_graphdb, get_neo4j
from app.schemas import ApiModel
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient
from services import reasoning_service

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


class ReasonResponse(ApiModel):
    activation: dict[str, float]
    facts: list[DerivedFactResponse]
    iterations: int
    converged_by: str


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
        facts=[
            DerivedFactResponse(
                id=f.id, fact=f.fact, confidence=f.confidence, iteration=f.iteration,
                source_id=f.source_id, target_id=f.target_id,
                rule_name=f.rule_name,
                proof_path=[
                    ProofStepResponse(
                        rule_name=step.rule_name,
                        edge_type=step.edge_type,
                        source_label=step.source_label,
                        target_label=step.target_label,
                        premise_activation=step.premise_activation,
                        iteration=step.iteration,
                        type_resolution=step.type_resolution,
                    )
                    for step in f.proof_path
                ],
            )
            for f in result.facts
        ],
        iterations=result.iterations,
        converged_by=result.converged_by,
    )
