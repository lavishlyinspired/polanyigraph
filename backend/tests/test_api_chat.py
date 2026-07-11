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
        self.last_call: dict[str, str] | None = None

    def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        self.last_call = {"system": system, "user": user}
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
    neo4j.run("MATCH (s:ChatSession {graphId: $gid}) DETACH DELETE s", gid=graph_id)
    neo4j.close()


def test_chat_returns_reply(client_and_graph):
    client, graph_id = client_and_graph
    resp = client.post(f"/chat/{graph_id}", json={"message": "What's in this graph?"})
    assert resp.status_code == 200
    assert resp.json()["reply"] == "Grounded real answer."


def test_chat_remembers_prior_turns_without_explicit_session_id(client_and_graph):
    """No session_id sent by the client -> defaults to one continuous session
    per graph, so existing frontend calls get real memory for free."""
    client, graph_id = client_and_graph
    from app.dependencies import get_llm
    from app.main import app

    llm2 = FakeLLM("second reply")
    client.post(f"/chat/{graph_id}", json={"message": "My favorite number is 42."})
    app.dependency_overrides[get_llm] = lambda: llm2
    client.post(f"/chat/{graph_id}", json={"message": "What's my favorite number?"})

    assert "My favorite number is 42." in llm2.last_call["system"]
