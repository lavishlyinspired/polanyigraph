"""API tests for manual node/edge construction (Construct tab's Add Node /
Add Edge). Validated against the live ontology -- a type or relation that
doesn't exist in the loaded ontology is rejected, matching how real
extraction is validated (kg-extraction SKILL.md), not freehand.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient


@pytest.fixture
def client_and_graph():
    settings = get_settings()
    neo4j = Neo4jClient(settings)
    graphdb = GraphDBClient(settings)
    try:
        neo4j.verify()
        graphdb.verify()
    except Exception:
        pytest.skip("Neo4j/GraphDB not reachable")

    from app.main import app

    graph_id = f"test-{uuid.uuid4().hex[:8]}"
    with TestClient(app) as test_client:
        yield test_client, graph_id

    neo4j.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)
    neo4j.close()
    graphdb.close()


def test_add_node_with_real_ontology_type(client_and_graph):
    client, graph_id = client_and_graph
    resp = client.post(f"/graph/{graph_id}/nodes", json={"label": "Acme Bank", "type": "organization"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["label"] == "Acme Bank"
    assert body["type"] == "organization"
    assert body["sourceDoc"] == "manual-entry"


def test_add_node_rejects_unknown_type(client_and_graph):
    client, graph_id = client_and_graph
    resp = client.post(f"/graph/{graph_id}/nodes", json={"label": "Something", "type": "not-a-real-ontology-class"})
    assert resp.status_code == 400


def test_add_node_is_idempotent_with_extraction_ids(client_and_graph):
    """Manually adding 'Acme Bank' twice merges into one node -- same id
    scheme as extraction, so a later real extraction of the same entity would
    merge into it too."""
    client, graph_id = client_and_graph
    client.post(f"/graph/{graph_id}/nodes", json={"label": "Acme Bank", "type": "organization"})
    client.post(f"/graph/{graph_id}/nodes", json={"label": "Acme Bank", "type": "organization"})

    graph_resp = client.get(f"/graph/{graph_id}")
    assert len(graph_resp.json()["nodes"]) == 1


def test_add_edge_with_real_ontology_relation(client_and_graph):
    client, graph_id = client_and_graph
    client.post(f"/graph/{graph_id}/nodes", json={"label": "Acme Bank", "type": "organization"})
    client.post(f"/graph/{graph_id}/nodes", json={"label": "Acme Stock", "type": "security"})
    graph_resp = client.get(f"/graph/{graph_id}")
    nodes = {n["label"]: n["id"] for n in graph_resp.json()["nodes"]}

    resp = client.post(
        f"/graph/{graph_id}/edges",
        json={"sourceId": nodes["Acme Bank"], "targetId": nodes["Acme Stock"], "type": "issues"},
    )
    assert resp.status_code == 200
    assert resp.json()["type"] == "issues"


def test_add_edge_rejects_unknown_relation(client_and_graph):
    client, graph_id = client_and_graph
    client.post(f"/graph/{graph_id}/nodes", json={"label": "A", "type": "organization"})
    client.post(f"/graph/{graph_id}/nodes", json={"label": "B", "type": "security"})
    graph_resp = client.get(f"/graph/{graph_id}")
    nodes = {n["label"]: n["id"] for n in graph_resp.json()["nodes"]}

    resp = client.post(
        f"/graph/{graph_id}/edges",
        json={"sourceId": nodes["A"], "targetId": nodes["B"], "type": "made-up-relation-xyz"},
    )
    assert resp.status_code == 400


def test_add_edge_rejects_unknown_nodes(client_and_graph):
    client, graph_id = client_and_graph
    resp = client.post(f"/graph/{graph_id}/edges", json={"sourceId": "nope-1", "targetId": "nope-2", "type": "issues"})
    assert resp.status_code == 400
