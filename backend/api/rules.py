"""Rules Manager: list (seed + custom), create custom, delete custom.

The hand-authored seed file (data/rules/fibo_rules.json) stays read-only and
non-deletable via the API -- it's curated, version-controlled config. Custom
rules added through the Construct tab are stored in Neo4j (services/rules_store.py),
validated against the real ontology (edge_type/source_type/target_type must
exist), and are the only ones deletable here. Both participate in reasoning
(see api/reason.py load_all_rules).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.dependencies import get_graphdb, get_neo4j
from app.schemas import ApiModel
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient
from ontology.loader import load_schema
from reasoning.rules_repo import load_rules
from services import rule_mining_service, rules_store

router = APIRouter(tags=["rules"])


class RuleResponse(ApiModel):
    id: str
    name: str
    edge_type: str
    source_type: str
    target_type: str
    threshold: float
    weight: float
    description: str
    source: str  # "seed" | "custom"


class RulesResponse(ApiModel):
    rules: list[RuleResponse]


class CreateRuleRequest(ApiModel):
    name: str
    edge_type: str
    source_type: str
    target_type: str
    threshold: float
    weight: float = 1.0
    description: str = "{source} -> {target}"


def _to_rule_response(r, *, source: str) -> RuleResponse:
    return RuleResponse(
        id=r.id, name=r.name, edge_type=r.edge_type, source_type=r.source_type,
        target_type=r.target_type, threshold=r.threshold, weight=r.weight,
        description=r.description, source=source,
    )


@router.get("/rules", response_model=RulesResponse, response_model_by_alias=True)
def get_rules(neo4j: Neo4jClient = Depends(get_neo4j)) -> RulesResponse:
    seed_by_id = {r.id: r for r in load_rules()}
    custom_by_id = {r.id: r for r in rules_store.list_custom_rules(neo4j)}
    # A Neo4j-stored rule with the same id as a seed rule is a weight
    # OVERRIDE (2026-07-13 plan §11.1's rule review), not a second distinct
    # rule -- show it once, tagged "seed" (that's still what it structurally
    # is), using the current (possibly-reviewed) values. See
    # rules_store.load_all_rules for why reasoning itself needs this same
    # dedup, not just this display.
    responses = [
        _to_rule_response(custom_by_id.get(rid, r), source="seed")
        for rid, r in seed_by_id.items()
    ]
    responses += [
        _to_rule_response(r, source="custom")
        for rid, r in custom_by_id.items()
        if rid not in seed_by_id
    ]
    return RulesResponse(rules=responses)


@router.post("/rules", response_model=RuleResponse, response_model_by_alias=True)
def create_rule(
    request: CreateRuleRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
    graphdb: GraphDBClient = Depends(get_graphdb),
    settings: Settings = Depends(get_settings),
) -> RuleResponse:
    schema = load_schema(graphdb, settings.graphdb_repository)
    known_properties = {p.lower() for p in schema.property_labels}
    if request.edge_type.lower() not in known_properties:
        raise HTTPException(status_code=400, detail=f"'{request.edge_type}' is not a known relation in the loaded ontology.")
    if not schema.is_known_type(request.source_type):
        raise HTTPException(status_code=400, detail=f"'{request.source_type}' is not a known type in the loaded ontology.")
    if not schema.is_known_type(request.target_type):
        raise HTTPException(status_code=400, detail=f"'{request.target_type}' is not a known type in the loaded ontology.")

    rule_id = f"custom-{uuid.uuid4().hex[:12]}"
    rules_store.create_rule(
        neo4j, rule_id=rule_id, name=request.name, edge_type=request.edge_type,
        source_type=request.source_type, target_type=request.target_type,
        threshold=request.threshold, weight=request.weight, description=request.description,
    )
    return RuleResponse(
        id=rule_id, name=request.name, edge_type=request.edge_type,
        source_type=request.source_type, target_type=request.target_type,
        threshold=request.threshold, weight=request.weight,
        description=request.description, source="custom",
    )


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: str, neo4j: Neo4jClient = Depends(get_neo4j)) -> dict[str, bool]:
    if not rule_id.startswith("custom-"):
        raise HTTPException(status_code=400, detail="Only custom rules can be deleted; seed rules are read-only.")
    deleted = rules_store.delete_rule(neo4j, rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found.")
    return {"deleted": True}


class CandidateRuleResponse(ApiModel):
    id: str
    edge_type: str
    source_type: str
    target_type: str
    support: int
    confidence: float
    status: str


class CandidateRulesResponse(ApiModel):
    candidates: list[CandidateRuleResponse]


def _to_candidate_response(c) -> CandidateRuleResponse:
    return CandidateRuleResponse(
        id=c.id, edge_type=c.edge_type, source_type=c.source_type, target_type=c.target_type,
        support=c.support, confidence=c.confidence, status=c.status,
    )


@router.post("/rules/mine/{graph_id}", response_model=CandidateRulesResponse, response_model_by_alias=True)
def mine_rules(graph_id: str, neo4j: Neo4jClient = Depends(get_neo4j)) -> CandidateRulesResponse:
    candidates = rule_mining_service.mine_candidates(neo4j, graph_id)
    return CandidateRulesResponse(candidates=[_to_candidate_response(c) for c in candidates])


@router.get("/rules/candidates", response_model=CandidateRulesResponse, response_model_by_alias=True)
def get_candidates(status: str = "pending", neo4j: Neo4jClient = Depends(get_neo4j)) -> CandidateRulesResponse:
    candidates = rule_mining_service.list_candidates(neo4j, status=status)
    return CandidateRulesResponse(candidates=[_to_candidate_response(c) for c in candidates])


@router.post("/rules/candidates/{candidate_id}/approve")
def approve_candidate_rule(candidate_id: str, neo4j: Neo4jClient = Depends(get_neo4j)) -> dict[str, bool]:
    try:
        rule_mining_service.approve_candidate(neo4j, candidate_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"approved": True}


@router.post("/rules/candidates/{candidate_id}/reject")
def reject_candidate_rule(candidate_id: str, neo4j: Neo4jClient = Depends(get_neo4j)) -> dict[str, bool]:
    try:
        rule_mining_service.reject_candidate(neo4j, candidate_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"rejected": True}
