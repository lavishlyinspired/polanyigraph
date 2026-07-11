"""POST /reason/{graph_id} — run the neurosymbolic loop (PLAN.md §8.4) and persist results."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.dependencies import get_graphdb, get_neo4j
from app.schemas import ApiModel
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient
from ontology.loader import load_schema
from reasoning.engine import reason as run_reasoning
from services import graph_service
from services.rules_store import load_all_rules

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


def _pick_source(nodes) -> str | None:
    """No source given: pick the highest out-degree-agnostic default — first node.

    MVP heuristic; a future version can rank by degree or let the UI pick.
    """
    return nodes[0].id if nodes else None


@router.post("/reason/{graph_id}", response_model=ReasonResponse, response_model_by_alias=True)
def reason_over_graph(
    graph_id: str,
    request: ReasonRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
    graphdb: GraphDBClient = Depends(get_graphdb),
    settings: Settings = Depends(get_settings),
) -> ReasonResponse:
    nodes, edges = graph_service.get_entities_and_edges_for_reasoning(neo4j, graph_id)
    if not nodes:
        raise HTTPException(status_code=404, detail=f"Graph '{graph_id}' has no entities to reason over.")

    source_id = request.source_id or _pick_source(nodes)
    if source_id not in {n.id for n in nodes}:
        raise HTTPException(status_code=400, detail=f"source_id '{source_id}' not found in graph '{graph_id}'.")

    rules = load_all_rules(neo4j)
    # Ontology-aware matching: rules reference generic ancestor types
    # ("organization") while real extraction returns specific subclasses
    # ("commercial bank") — see docs/MVP_PLAN.md §12.
    schema = load_schema(graphdb, settings.graphdb_repository)
    type_matches = schema.build_subclass_matcher()
    result = run_reasoning(
        nodes, edges, rules, source_id,
        decay=settings.reason_decay,
        epsilon=settings.reason_epsilon,
        max_iterations=settings.reason_max_iterations,
        type_matches=type_matches,
    )

    graph_service.apply_activation(neo4j, graph_id=graph_id, activation=result.activation)
    graph_service.save_derived_facts(neo4j, graph_id=graph_id, facts=list(result.facts))

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
