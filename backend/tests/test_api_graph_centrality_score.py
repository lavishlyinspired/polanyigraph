"""Verifies GET /graph/{graph_id} exposes a written-back centralityScore
in the JSON response, closing the gap browser verification found: the
analytics engine could persist it, but nothing in the read path surfaced
it to the frontend (PLAN: plans/analytical-engine.md Slice 9).
"""

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
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="a1", label="A", type_="organization", source_doc="d", extraction_confidence=1.0)
    neo4j.run("MATCH (e:Entity {id: $id, graphId: $gid}) SET e.centralityScore = $score", id="a1", gid=graph_id, score=0.6)

    with TestClient(app) as test_client:
        yield test_client, graph_id

    neo4j.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)
    neo4j.close()


def test_get_graph_response_includes_centrality_score(client_and_graph):
    client, graph_id = client_and_graph

    resp = client.get(f"/graph/{graph_id}")

    assert resp.status_code == 200
    node = next(n for n in resp.json()["nodes"] if n["id"] == "a1")
    assert node["centralityScore"] == 0.6
