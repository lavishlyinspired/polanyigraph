"""API tests for rule mining endpoints (2026-07-13 plan §5): mine, list
candidates, approve, reject."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from db.neo4j_client import Neo4jClient
from services import graph_service


@pytest.fixture
def client_and_neo4j():
    settings = get_settings()
    neo4j = Neo4jClient(settings)
    try:
        neo4j.verify()
    except Exception:
        pytest.skip("Neo4j not reachable")

    from app.main import app

    graph_id = f"test-{uuid.uuid4().hex[:8]}"
    created_candidate_ids: list[str] = []
    created_rule_ids: list[str] = []
    with TestClient(app) as test_client:
        yield test_client, neo4j, graph_id, created_candidate_ids, created_rule_ids

    neo4j.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)
    for cid in created_candidate_ids:
        neo4j.run("MATCH (c:CandidateRule {id: $id}) DETACH DELETE c", id=cid)
    for rid in created_rule_ids:
        neo4j.run("MATCH (r:Rule {id: $id}) DETACH DELETE r", id=rid)
    neo4j.close()


def test_mine_endpoint_returns_candidates_for_a_repeating_pattern(client_and_neo4j):
    client, neo4j, graph_id, created_candidate_ids, _ = client_and_neo4j
    tag = uuid.uuid4().hex[:8]
    edge_type = f"OWNS_{tag}"
    for i in range(3):
        graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id=f"org{i}", label=f"Org {i}", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="target_org", label="Target Org", type_="organization", source_doc="d", extraction_confidence=1.0)
    for i in range(3):
        graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id=f"e{i}", source_id=f"org{i}", target_id="target_org", type_=edge_type, weight=1.0)

    resp = client.post(f"/rules/mine/{graph_id}")

    assert resp.status_code == 200
    body = resp.json()
    created_candidate_ids.extend(c["id"] for c in body["candidates"])
    match = next(c for c in body["candidates"] if c["edgeType"] == edge_type)
    assert match["support"] == 3
    assert match["status"] == "pending"


def test_get_candidates_lists_pending_by_default(client_and_neo4j):
    client, neo4j, graph_id, created_candidate_ids, _ = client_and_neo4j
    tag = uuid.uuid4().hex[:8]
    edge_type = f"PARTNERS_{tag}"
    for i in range(3):
        graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id=f"org{i}", label=f"Org {i}", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="target_org", label="Target Org", type_="organization", source_doc="d", extraction_confidence=1.0)
    for i in range(3):
        graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id=f"e{i}", source_id=f"org{i}", target_id="target_org", type_=edge_type, weight=1.0)
    mined = client.post(f"/rules/mine/{graph_id}").json()["candidates"]
    created_candidate_ids.extend(c["id"] for c in mined)

    resp = client.get("/rules/candidates", params={"status": "pending"})

    assert resp.status_code == 200
    assert any(c["edgeType"] == edge_type for c in resp.json()["candidates"])


def test_approve_candidate_endpoint_promotes_it_to_a_real_rule(client_and_neo4j):
    client, neo4j, graph_id, created_candidate_ids, created_rule_ids = client_and_neo4j
    tag = uuid.uuid4().hex[:8]
    edge_type = f"AFFILIATED_{tag}"
    for i in range(3):
        graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id=f"org{i}", label=f"Org {i}", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="target_org", label="Target Org", type_="organization", source_doc="d", extraction_confidence=1.0)
    for i in range(3):
        graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id=f"e{i}", source_id=f"org{i}", target_id="target_org", type_=edge_type, weight=1.0)
    mined = client.post(f"/rules/mine/{graph_id}").json()["candidates"]
    created_candidate_ids.extend(c["id"] for c in mined)
    candidate_id = next(c["id"] for c in mined if c["edgeType"] == edge_type)
    created_rule_ids.append(f"mined-{candidate_id}")

    resp = client.post(f"/rules/candidates/{candidate_id}/approve")

    assert resp.status_code == 200
    rules = client.get("/rules").json()["rules"]
    assert any(r["id"] == f"mined-{candidate_id}" for r in rules)


def test_reject_candidate_endpoint_marks_it_rejected(client_and_neo4j):
    client, neo4j, graph_id, created_candidate_ids, _ = client_and_neo4j
    tag = uuid.uuid4().hex[:8]
    edge_type = f"SUPPLIES_{tag}"
    for i in range(3):
        graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id=f"org{i}", label=f"Org {i}", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="target_org", label="Target Org", type_="organization", source_doc="d", extraction_confidence=1.0)
    for i in range(3):
        graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id=f"e{i}", source_id=f"org{i}", target_id="target_org", type_=edge_type, weight=1.0)
    mined = client.post(f"/rules/mine/{graph_id}").json()["candidates"]
    created_candidate_ids.extend(c["id"] for c in mined)
    candidate_id = next(c["id"] for c in mined if c["edgeType"] == edge_type)

    resp = client.post(f"/rules/candidates/{candidate_id}/reject")

    assert resp.status_code == 200
    pending = client.get("/rules/candidates", params={"status": "pending"}).json()["candidates"]
    assert not any(c["id"] == candidate_id for c in pending)
    rejected = client.get("/rules/candidates", params={"status": "rejected"}).json()["candidates"]
    assert any(c["id"] == candidate_id for c in rejected)


def test_approve_unknown_candidate_returns_404(client_and_neo4j):
    client, _, _, _, _ = client_and_neo4j
    resp = client.post("/rules/candidates/no-such-candidate/approve")
    assert resp.status_code == 404
