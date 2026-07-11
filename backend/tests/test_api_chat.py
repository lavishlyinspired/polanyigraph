"""API-level test for POST /chat/{graph_id}."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
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
    try:
        neo4j.verify()
    except Exception:
        pytest.skip("Neo4j not reachable")

    from app.dependencies import get_llm
    from app.main import app

    graph_id = f"test-{uuid.uuid4().hex[:8]}"
    app.dependency_overrides[get_llm] = lambda: FakeLLM("Grounded real answer.")

    with TestClient(app) as test_client:
        yield test_client, graph_id

    app.dependency_overrides.clear()
    neo4j.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)
    neo4j.close()


def test_chat_returns_reply(client_and_graph):
    client, graph_id = client_and_graph
    resp = client.post(f"/chat/{graph_id}", json={"message": "What's in this graph?"})
    assert resp.status_code == 200
    assert resp.json()["reply"] == "Grounded real answer."
