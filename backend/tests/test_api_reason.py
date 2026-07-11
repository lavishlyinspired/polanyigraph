"""API-level test for POST /reason/{graph_id} against a live Neo4j-seeded graph."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from db.neo4j_client import Neo4jClient
from services import graph_service


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
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="org1", label="Acme Corp", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="sec1", label="Acme Preferred Stock", type_="security", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id="e1", source_id="org1", target_id="sec1", type_="issues", weight=1.0)

    with TestClient(app) as test_client:
        yield test_client, graph_id

    neo4j.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)
    neo4j.run("MATCH (f:DerivedFact {graphId: $gid}) DETACH DELETE f", gid=graph_id)
    neo4j.close()


def test_reason_derives_fact_from_real_fibo_rule(client_and_graph):
    client, graph_id = client_and_graph

    resp = client.post(f"/reason/{graph_id}", json={"sourceId": "org1"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["convergedBy"] in {"fixpoint", "max_iterations"}
    fact_texts = {f["fact"] for f in body["facts"]}
    assert "Acme Corp issues Acme Preferred Stock" in fact_texts


def test_reason_404s_on_empty_graph(client_and_graph):
    client, _ = client_and_graph
    resp = client.post("/reason/no-such-graph-xyz", json={})
    assert resp.status_code == 404


@pytest.fixture
def real_subclass_graph():
    """Reproduces the exact scenario discovered via live browser testing:
    extraction returns real FIBO subclasses, not the rules' generic types."""
    settings = get_settings()
    neo4j = Neo4jClient(settings)
    try:
        neo4j.verify()
    except Exception:
        pytest.skip("Neo4j not reachable")

    from app.main import app

    graph_id = f"test-{uuid.uuid4().hex[:8]}"
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="bank1", label="Deutsche Bank AG", type_="commercial bank", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="ecb1", label="European Central Bank", type_="central bank", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id="e1", source_id="bank1", target_id="ecb1", type_="is regulated by", weight=1.0)

    with TestClient(app) as test_client:
        yield test_client, graph_id

    neo4j.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)
    neo4j.run("MATCH (f:DerivedFact {graphId: $gid}) DETACH DELETE f", gid=graph_id)
    neo4j.close()


def test_reason_derives_fact_across_real_fibo_subclasses(real_subclass_graph):
    """The exact live-browser-discovered gap (docs/MVP_PLAN.md §12), now fixed:
    'commercial bank' satisfies the rule's 'organization', 'central bank'
    satisfies 'regulatory agency', via real rdfs:subClassOf edges."""
    client, graph_id = real_subclass_graph

    resp = client.post(f"/reason/{graph_id}", json={"sourceId": "bank1"})

    assert resp.status_code == 200
    body = resp.json()
    fact_texts = {f["fact"] for f in body["facts"]}
    assert "Deutsche Bank AG is regulated by European Central Bank" in fact_texts

    fact = next(f for f in body["facts"] if f["fact"] == "Deutsche Bank AG is regulated by European Central Bank")
    resolution = fact["proofPath"][-1]["typeResolution"]
    assert resolution is not None
    assert "commercial bank" in resolution
    assert "central bank" in resolution
