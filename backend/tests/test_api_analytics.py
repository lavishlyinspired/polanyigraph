"""API-level tests for the analytics engine's walking-skeleton routes
(PLAN: plans/analytical-engine.md Slice 1). POST /analytics/run uses a
hardcoded single-algorithm dispatch in this slice -- the registry (and
its own tests) arrive in Slice 2.
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
    for eid, label in [("h", "Hub"), ("a", "Leaf A"), ("b", "Leaf B")]:
        graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id=eid, label=label, type_="organization", source_doc="d", extraction_confidence=1.0)
    # Different relation types from the same source -- upsert_relationship treats a
    # same-source-and-type edge to a different target as superseding, not additive
    # (see its docstring), so same-type would collapse this to a single live edge.
    graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id="e1", source_id="h", target_id="a", type_="owns", weight=1.0)
    graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id="e2", source_id="h", target_id="b", type_="manages", weight=1.0)

    with TestClient(app) as test_client:
        yield test_client, graph_id

    neo4j.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)
    neo4j.close()


def test_create_projection_returns_node_and_edge_counts(client_and_graph):
    client, graph_id = client_and_graph

    resp = client.post(f"/analytics/projections/{graph_id}", json={"name": "p1"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "p1"
    assert body["nodeCount"] == 3
    assert body["edgeCount"] == 2


def test_create_projection_defaults_name_to_graph_id(client_and_graph):
    client, graph_id = client_and_graph

    resp = client.post(f"/analytics/projections/{graph_id}", json={})

    assert resp.status_code == 200
    assert resp.json()["name"] == graph_id


def test_run_degree_centrality_on_a_projection(client_and_graph):
    client, graph_id = client_and_graph
    client.post(f"/analytics/projections/{graph_id}", json={"name": "p1"})

    resp = client.post("/analytics/run", json={"projection": "p1", "algorithm": "degree_centrality"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["algorithm"] == "degree_centrality"
    assert body["projection"] == "p1"
    assert body["nodeScores"]["h"] > body["nodeScores"]["a"]
    assert body["suggestedChart"] == "bar"


def test_run_against_unknown_projection_returns_404(client_and_graph):
    client, _graph_id = client_and_graph

    resp = client.post("/analytics/run", json={"projection": "does-not-exist", "algorithm": "degree_centrality"})

    assert resp.status_code == 404


def test_run_unknown_algorithm_returns_400(client_and_graph):
    client, graph_id = client_and_graph
    client.post(f"/analytics/projections/{graph_id}", json={"name": "p1"})

    resp = client.post("/analytics/run", json={"projection": "p1", "algorithm": "not_a_real_algorithm"})

    assert resp.status_code == 400


def test_run_degree_centrality_role_weights_a_noisy_value_entity_to_zero(client_and_graph):
    """The exact live-UI bug this Phase 1 fix addresses (2026-07-14): running
    degree_centrality from the Analytics page must no longer rank a "rate of
    return"-typed entity (a real FIBO subclass of quantity value) above real
    actors purely by co-occurrence."""
    client, graph_id = client_and_graph
    from db.neo4j_client import Neo4jClient
    from app.config import get_settings
    from services import graph_service

    neo4j = Neo4jClient(get_settings())
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="rate", label="8.45%", type_="rate of return", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id="e3", source_id="h", target_id="rate", type_="reports", weight=1.0)
    neo4j.close()

    client.post(f"/analytics/projections/{graph_id}", json={"name": "p-roles"})
    resp = client.post("/analytics/run", json={"projection": "p-roles", "algorithm": "degree_centrality"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["nodeScores"]["rate"] == 0.0
    assert body["nodeScores"]["h"] > 0.0


def test_run_pagerank_via_registry_dispatch(client_and_graph):
    """Verifies registry-based dispatch reaches pagerank end-to-end; pagerank's
    own ranking correctness (direction-sensitive) is covered by the unit test
    in test_analytics_centrality.py against a fixture built for that."""
    client, graph_id = client_and_graph
    client.post(f"/analytics/projections/{graph_id}", json={"name": "p1"})

    resp = client.post("/analytics/run", json={"projection": "p1", "algorithm": "pagerank"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["algorithm"] == "pagerank"
    assert set(body["nodeScores"]) == {"h", "a", "b"}
    assert abs(sum(body["nodeScores"].values()) - 1.0) < 1e-6


def test_list_algorithms_includes_all_centrality_algorithms(client_and_graph):
    client, _graph_id = client_and_graph

    resp = client.get("/analytics/algorithms")

    assert resp.status_code == 200
    names = {a["name"] for a in resp.json()["algorithms"]}
    assert {"degree_centrality", "pagerank", "betweenness_centrality", "closeness_centrality"} <= names
    categories = {a["category"] for a in resp.json()["algorithms"] if a["name"] == "pagerank"}
    assert categories == {"centrality"}


def test_create_projection_on_empty_graph_returns_400(client_and_graph):
    client, _graph_id = client_and_graph
    empty_graph_id = f"empty-{uuid.uuid4().hex[:8]}"

    resp = client.post(f"/analytics/projections/{empty_graph_id}", json={"name": "p-empty"})

    assert resp.status_code == 400


def test_list_projections_includes_created_projection(client_and_graph):
    client, graph_id = client_and_graph
    client.post(f"/analytics/projections/{graph_id}", json={"name": "p-list-me"})

    resp = client.get("/analytics/projections")

    assert resp.status_code == 200
    names = {p["name"] for p in resp.json()["projections"]}
    assert "p-list-me" in names


def test_drop_projection_removes_it(client_and_graph):
    client, graph_id = client_and_graph
    client.post(f"/analytics/projections/{graph_id}", json={"name": "p-to-drop"})

    drop_resp = client.delete("/analytics/projections/p-to-drop")
    assert drop_resp.status_code == 200

    run_resp = client.post("/analytics/run", json={"projection": "p-to-drop", "algorithm": "degree_centrality"})
    assert run_resp.status_code == 404


def test_drop_unknown_projection_returns_404(client_and_graph):
    client, _graph_id = client_and_graph

    resp = client.delete("/analytics/projections/does-not-exist")

    assert resp.status_code == 404


def test_persist_writes_scores_back_to_neo4j(client_and_graph):
    client, graph_id = client_and_graph
    client.post(f"/analytics/projections/{graph_id}", json={"name": "p-persist"})

    resp = client.post(
        "/analytics/persist",
        json={"projection": "p-persist", "algorithm": "degree_centrality", "propertyName": "centralityScore"},
    )

    assert resp.status_code == 200

    from db.neo4j_client import Neo4jClient
    from app.config import get_settings

    verify_client = Neo4jClient(get_settings())
    rows = verify_client.run(
        "MATCH (e:Entity {id: $id, graphId: $gid}) RETURN e.centralityScore AS score", id="h", gid=graph_id
    )
    assert rows[0]["score"] is not None
    verify_client.close()


def test_persist_against_unknown_projection_returns_404(client_and_graph):
    client, _graph_id = client_and_graph

    resp = client.post(
        "/analytics/persist",
        json={"projection": "does-not-exist", "algorithm": "degree_centrality", "propertyName": "x"},
    )

    assert resp.status_code == 404
