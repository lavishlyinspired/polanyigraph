"""Integration tests for rule mining (2026-07-13 plan §5): finds which
(edge_type, source_type, target_type) combinations already occur often and
consistently enough in a graph's real extracted data to deserve becoming a
scored, watchable Rule -- automating what a human currently does by hand-
authoring data/rules/fibo_rules.json entries, not a two-relation composition
miner (out of scope, see plan's "Corrected scope" section).

Real Neo4j, no mocks, per project convention. Edge-type strings are
uuid-suffixed per test so re-runs and parallel tests never collide with each
other, real ontology relations, or leftover state from a prior run.
"""

from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient
from services import graph_service, reasoning_service, rule_mining_service, rules_store


@pytest.fixture
def neo4j():
    client = Neo4jClient(get_settings())
    try:
        client.verify()
    except Exception:
        pytest.skip("Neo4j not reachable")
    graph_id = f"test-{uuid.uuid4().hex[:8]}"
    created_candidate_ids: list[str] = []
    created_rule_ids: list[str] = []
    yield client, graph_id, created_candidate_ids, created_rule_ids
    client.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)
    client.run("MATCH (f:DerivedFact {graphId: $gid}) DETACH DELETE f", gid=graph_id)
    for cid in created_candidate_ids:
        client.run("MATCH (c:CandidateRule {id: $id}) DETACH DELETE c", id=cid)
    for rid in created_rule_ids:
        client.run("MATCH (r:Rule {id: $id}) DETACH DELETE r", id=rid)
    client.close()


def _tag() -> str:
    return uuid.uuid4().hex[:8]


def test_mine_candidates_finds_a_repeating_pattern_with_correct_support_and_confidence(neo4j):
    client, graph_id, created_candidate_ids, _ = neo4j
    tag = _tag()
    regulated_by = f"REGULATED_BY_{tag}"
    domiciled_in = f"DOMICILED_IN_{tag}"

    for i in range(5):
        graph_service.upsert_entity(client, graph_id=graph_id, entity_id=f"org{i}", label=f"Org {i}", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="agency1", label="Agency", type_="regulatory agency", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="juris1", label="Jurisdiction", type_="jurisdiction", source_doc="d", extraction_confidence=1.0)
    for i in range(5):
        graph_service.upsert_relationship(client, graph_id=graph_id, edge_id=f"reg{i}", source_id=f"org{i}", target_id="agency1", type_=regulated_by, weight=1.0)
    for i in range(4):
        graph_service.upsert_relationship(client, graph_id=graph_id, edge_id=f"dom{i}", source_id=f"org{i}", target_id="juris1", type_=domiciled_in, weight=1.0)

    candidates = rule_mining_service.mine_candidates(client, graph_id, min_support=3, min_confidence=0.3)
    created_candidate_ids.extend(c.id for c in candidates)

    match = next(c for c in candidates if c.edge_type == domiciled_in)
    assert match.source_type == "organization"
    assert match.target_type == "jurisdiction"
    assert match.support == 4
    # confidence = support / (all organization-outgoing edges) = 4 / (5 + 4)
    assert match.confidence == pytest.approx(4 / 9)


def test_mine_candidates_never_proposes_a_combo_already_covered_by_a_seed_rule(neo4j):
    client, graph_id, created_candidate_ids, _ = neo4j
    for i in range(5):
        graph_service.upsert_entity(client, graph_id=graph_id, entity_id=f"org{i}", label=f"Org {i}", type_="organization", source_doc="d", extraction_confidence=1.0)
        graph_service.upsert_entity(client, graph_id=graph_id, entity_id=f"sec{i}", label=f"Security {i}", type_="security", source_doc="d", extraction_confidence=1.0)
        graph_service.upsert_relationship(client, graph_id=graph_id, edge_id=f"iss{i}", source_id=f"org{i}", target_id=f"sec{i}", type_="issues", weight=1.0)

    candidates = rule_mining_service.mine_candidates(client, graph_id, min_support=3, min_confidence=0.3)
    created_candidate_ids.extend(c.id for c in candidates)

    assert not any(c.edge_type == "issues" and c.source_type == "organization" and c.target_type == "security" for c in candidates)


def test_mine_candidates_produces_nothing_on_a_graph_too_small_for_a_pattern(neo4j):
    client, graph_id, created_candidate_ids, _ = neo4j
    tag = _tag()
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="org0", label="Org", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="sec0", label="Sec", type_="security", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(client, graph_id=graph_id, edge_id="e0", source_id="org0", target_id="sec0", type_=f"RARE_{tag}", weight=1.0)

    candidates = rule_mining_service.mine_candidates(client, graph_id)
    created_candidate_ids.extend(c.id for c in candidates)

    assert candidates == []


def test_reject_candidate_is_not_resurfaced_by_a_later_mining_run(neo4j):
    client, graph_id, created_candidate_ids, _ = neo4j
    tag = _tag()
    owns = f"OWNS_{tag}"
    for i in range(3):
        graph_service.upsert_entity(client, graph_id=graph_id, entity_id=f"org{i}", label=f"Org {i}", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="target_org", label="Target Org", type_="organization", source_doc="d", extraction_confidence=1.0)
    for i in range(3):
        graph_service.upsert_relationship(client, graph_id=graph_id, edge_id=f"own{i}", source_id=f"org{i}", target_id="target_org", type_=owns, weight=1.0)

    first_pass = rule_mining_service.mine_candidates(client, graph_id, min_support=3, min_confidence=0.3)
    created_candidate_ids.extend(c.id for c in first_pass)
    candidate = next(c for c in first_pass if c.edge_type == owns)

    rule_mining_service.reject_candidate(client, candidate.id)
    second_pass = rule_mining_service.mine_candidates(client, graph_id, min_support=3, min_confidence=0.3)
    created_candidate_ids.extend(c.id for c in second_pass)

    assert not any(c.edge_type == owns for c in second_pass)
    assert rule_mining_service.list_candidates(client, status="rejected")
    assert candidate.id in {c.id for c in rule_mining_service.list_candidates(client, status="rejected")}


def test_approve_candidate_creates_a_real_rule_that_fires_in_reasoning(neo4j):
    client, graph_id, created_candidate_ids, created_rule_ids = neo4j
    settings = get_settings()
    graphdb = GraphDBClient(settings)
    try:
        graphdb.verify()
    except Exception:
        pytest.skip("GraphDB not reachable")
    tag = _tag()
    partners_with = f"PARTNERS_WITH_{tag}"

    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="orgA", label="Org A", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="orgB", label="Org B", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="orgC", label="Org C", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="orgD", label="Org D", type_="organization", source_doc="d", extraction_confidence=1.0)
    for i, src in enumerate(["orgA", "orgB", "orgC"]):
        graph_service.upsert_relationship(client, graph_id=graph_id, edge_id=f"pw{i}", source_id=src, target_id="orgD", type_=partners_with, weight=1.0)

    candidates = rule_mining_service.mine_candidates(client, graph_id, min_support=3, min_confidence=0.3)
    created_candidate_ids.extend(c.id for c in candidates)
    candidate = next(c for c in candidates if c.edge_type == partners_with)
    created_rule_ids.append(f"mined-{candidate.id}")

    rule_mining_service.approve_candidate(client, candidate.id)

    assert f"mined-{candidate.id}" in {r.id for r in rules_store.list_custom_rules(client)}

    result = reasoning_service.run_reasoning(client, graphdb, settings, graph_id=graph_id, source_id="orgA")
    fact_texts = {f.fact for f in result.facts}
    assert f"Org A {partners_with} Org D (mined, support={candidate.support})" in fact_texts

    graphdb.close()
