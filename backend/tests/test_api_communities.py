"""API-level tests for community detection (PLAN.md §20 item 5)."""

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
        neo4j.run("RETURN gds.version() AS version")
    except Exception:
        pytest.skip("Neo4j/GDS not reachable")

    from app.main import app

    graph_id = f"test-{uuid.uuid4().hex[:8]}"

    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="a1", label="Acme Corp", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="a2", label="Acme Holdings", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id="e1", source_id="a1", target_id="a2", type_="owns", weight=1.0)

    with TestClient(app) as test_client:
        yield test_client, graph_id

    neo4j.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)
    neo4j.close()


def test_post_communities_runs_detection_and_returns_members(client_and_graph):
    client, graph_id = client_and_graph

    resp = client.post(f"/graph/{graph_id}/communities")

    assert resp.status_code == 200
    members = resp.json()["members"]
    assert len(members) == 2
    assert {m["entityId"] for m in members} == {"a1", "a2"}
    assert members[0]["communityId"] == members[1]["communityId"]


def test_get_communities_reads_without_recomputing(client_and_graph):
    client, graph_id = client_and_graph
    client.post(f"/graph/{graph_id}/communities")

    resp = client.get(f"/graph/{graph_id}/communities")

    assert resp.status_code == 200
    assert len(resp.json()["members"]) == 2


def test_get_communities_empty_before_detection_runs(client_and_graph):
    client, graph_id = client_and_graph
    resp = client.get(f"/graph/{graph_id}/communities")
    assert resp.json()["members"] == []


def test_graph_response_carries_community_id_after_detection(client_and_graph):
    client, graph_id = client_and_graph
    client.post(f"/graph/{graph_id}/communities")

    graph = client.get(f"/graph/{graph_id}").json()

    a1 = next(n for n in graph["nodes"] if n["id"] == "a1")
    assert a1["communityId"] is not None
