"""API-level tests for the Reason tab's manual step-by-step mode (prototype
parity): POST /reason/{graphId}/spread, /infer, /feedback, and the two
clear endpoints, plus GET /reason/{graphId}/facts to read current state."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from db.neo4j_client import Neo4jClient
from services import graph_service
from services.rules_store import create_rule


@pytest.fixture
def client_and_graph():
    settings = get_settings()
    neo4j = Neo4jClient(settings)
    try:
        neo4j.verify()
    except Exception:
        pytest.skip("Neo4j not reachable")

    from app.main import app

    graph_id = f"test-{uuid.uuid4().hex[:8]}"
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="A", label="A", type_="T", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="B", label="B", type_="T", source_doc="d", extraction_confidence=1.0)
    rule_id = f"{graph_id}:test-rule"
    create_rule(neo4j, rule_id=rule_id, name="test-hop-rule", edge_type="test-hop-edge", source_type="T", target_type="T", threshold=0.6, weight=1.0, description="{source} -> {target}")
    graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id="e1", source_id="A", target_id="B", type_="test-hop-edge", weight=1.0)

    with TestClient(app) as test_client:
        yield test_client, graph_id

    neo4j.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)
    neo4j.run("MATCH (f:DerivedFact {graphId: $gid}) DETACH DELETE f", gid=graph_id)
    neo4j.run("MATCH (r:Rule {id: $rid}) DETACH DELETE r", rid=rule_id)
    neo4j.close()


def test_full_manual_step_lifecycle(client_and_graph):
    client, graph_id = client_and_graph

    # 1. Spread activation alone.
    spread_resp = client.post(f"/reason/{graph_id}/spread", json={"sourceId": "A"})
    assert spread_resp.status_code == 200
    assert spread_resp.json()["activation"]["A"] == 1.0

    # 2. Run inference alone -- fires on the persisted activation from step 1.
    infer_resp = client.post(f"/reason/{graph_id}/infer")
    assert infer_resp.status_code == 200
    infer_body = infer_resp.json()
    assert len(infer_body["facts"]) == 1
    assert infer_body["facts"][0]["fedBack"] is False
    assert len(infer_body["trace"]) == 1
    assert infer_body["trace"][0]["fired"] is True

    # 3. Read current facts state independently of the infer response.
    facts_resp = client.get(f"/reason/{graph_id}/facts")
    assert facts_resp.status_code == 200
    assert len(facts_resp.json()["facts"]) == 1

    # 4. Feed back alone -- boosts B's activation, marks the fact fed back.
    feedback_resp = client.post(f"/reason/{graph_id}/feedback")
    assert feedback_resp.status_code == 200
    assert feedback_resp.json()["activation"]["B"] > 0

    facts_after_feedback = client.get(f"/reason/{graph_id}/facts").json()["facts"]
    assert facts_after_feedback[0]["fedBack"] is True

    # 5. Clear facts.
    clear_facts_resp = client.post(f"/reason/{graph_id}/clear-facts")
    assert clear_facts_resp.status_code == 200
    assert client.get(f"/reason/{graph_id}/facts").json()["facts"] == []

    # 6. Clear activation.
    clear_activation_resp = client.post(f"/reason/{graph_id}/clear-activation")
    assert clear_activation_resp.status_code == 200
    graph = client.get(f"/graph/{graph_id}").json()
    assert all(n["activation"] == 0.0 for n in graph["nodes"])


def test_spread_404s_on_empty_graph(client_and_graph):
    client, _ = client_and_graph
    resp = client.post("/reason/no-such-graph-xyz/spread", json={})
    assert resp.status_code == 404


def test_infer_404s_on_empty_graph(client_and_graph):
    client, _ = client_and_graph
    resp = client.post("/reason/no-such-graph-xyz/infer")
    assert resp.status_code == 404
