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
from services import rules_store

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


@router.get("/rules", response_model=RulesResponse, response_model_by_alias=True)
def get_rules(neo4j: Neo4jClient = Depends(get_neo4j)) -> RulesResponse:
    seed = [
        RuleResponse(
            id=r.id, name=r.name, edge_type=r.edge_type, source_type=r.source_type,
            target_type=r.target_type, threshold=r.threshold, weight=r.weight,
            description=r.description, source="seed",
        )
        for r in load_rules()
    ]
    custom = [
        RuleResponse(
            id=r.id, name=r.name, edge_type=r.edge_type, source_type=r.source_type,
            target_type=r.target_type, threshold=r.threshold, weight=r.weight,
            description=r.description, source="custom",
        )
        for r in rules_store.list_custom_rules(neo4j)
    ]
    return RulesResponse(rules=seed + custom)


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
