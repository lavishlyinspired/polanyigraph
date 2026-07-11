"""API tests for custom rule create/delete (Rules Manager)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient


@pytest.fixture
def client_and_neo4j():
    settings = get_settings()
    neo4j = Neo4jClient(settings)
    graphdb = GraphDBClient(settings)
    try:
        neo4j.verify()
        graphdb.verify()
    except Exception:
        pytest.skip("Neo4j/GraphDB not reachable")

    from app.main import app

    created_ids: list[str] = []
    with TestClient(app) as test_client:
        yield test_client, created_ids

    for rid in created_ids:
        neo4j.run("MATCH (r:Rule {id: $rid}) DETACH DELETE r", rid=rid)
    neo4j.close()
    graphdb.close()


def test_create_custom_rule_with_real_ontology_vocabulary(client_and_neo4j):
    client, created_ids = client_and_neo4j
    resp = client.post(
        "/rules",
        json={
            "name": "Custom Regulatory Rule",
            "edgeType": "issues",
            "sourceType": "organization",
            "targetType": "security",
            "threshold": 0.5,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    created_ids.append(body["id"])
    assert body["source"] == "custom"
    assert body["id"].startswith("custom-")

    listed = client.get("/rules").json()["rules"]
    assert any(r["id"] == body["id"] for r in listed)


def test_create_custom_rule_rejects_unknown_relation(client_and_neo4j):
    client, _ = client_and_neo4j
    resp = client.post(
        "/rules",
        json={"name": "Bad", "edgeType": "not-a-real-relation", "sourceType": "organization", "targetType": "security", "threshold": 0.5},
    )
    assert resp.status_code == 400


def test_delete_custom_rule(client_and_neo4j):
    client, created_ids = client_and_neo4j
    created = client.post(
        "/rules",
        json={"name": "To Delete", "edgeType": "issues", "sourceType": "organization", "targetType": "security", "threshold": 0.5},
    ).json()

    resp = client.delete(f"/rules/{created['id']}")
    assert resp.status_code == 200

    listed = client.get("/rules").json()["rules"]
    assert not any(r["id"] == created["id"] for r in listed)


def test_cannot_delete_seed_rule(client_and_neo4j):
    client, _ = client_and_neo4j
    seed_rules = [r for r in client.get("/rules").json()["rules"] if r["source"] == "seed"]
    resp = client.delete(f"/rules/{seed_rules[0]['id']}")
    assert resp.status_code == 400
