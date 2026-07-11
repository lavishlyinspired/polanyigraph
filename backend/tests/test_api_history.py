"""API-level test for GET /history/{graph_id}."""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient


class FakeLLM:
    def __init__(self, response: str) -> None:
        self._response = response

    def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        return self._response


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
    from app.dependencies import get_llm

    graph_id = f"test-{uuid.uuid4().hex[:8]}"
    payload = json.dumps({
        "entities": [{"name": "Acme Corp", "type": "organization", "confidence": 0.9}],
        "relationships": [],
    })
    app.dependency_overrides[get_llm] = lambda: FakeLLM(payload)

    with TestClient(app) as test_client:
        yield test_client, graph_id

    app.dependency_overrides.clear()
    neo4j.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)
    neo4j.run("MATCH (h:IngestEvent {graphId: $gid}) DETACH DELETE h", gid=graph_id)
    neo4j.close()
    graphdb.close()


def test_history_reflects_real_posted_text(client_and_graph):
    client, graph_id = client_and_graph

    client.post("/ingest", json={"graphId": graph_id, "source": {"type": "text", "text": "Acme Corp filed a report."}})

    resp = client.get(f"/history/{graph_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["events"]) == 1
    assert body["events"][0]["text"] == "Acme Corp filed a report."
    assert body["events"][0]["entityCount"] == 1


def test_history_empty_for_unknown_graph(client_and_graph):
    client, _ = client_and_graph
    resp = client.get("/history/no-such-graph-xyz")
    assert resp.status_code == 200
    assert resp.json()["events"] == []
