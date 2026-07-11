"""API-level test for PATCH /graph/{graphId}/nodes/{nodeId}."""

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


def test_patch_node_updates_salience_properties_note(client_and_graph):
    client, graph_id = client_and_graph
    created = client.post(f"/graph/{graph_id}/nodes", json={"label": "Acme Bank", "type": "organization"}).json()

    resp = client.patch(
        f"/graph/{graph_id}/nodes/{created['id']}",
        json={"salience": 1.7, "properties": {"sector": "Banking"}, "note": "key node"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["salience"] == 1.7
    assert body["properties"] == {"sector": "Banking"}
    assert body["note"] == "key node"
