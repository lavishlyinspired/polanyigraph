"""API-level test for POST /agent/{graph_id} (MVP_PLAN.md Phase 6)."""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient


class FakeLLM:
    def __init__(self, extraction_payload: str, reply: str = "Done.", route: str | None = None) -> None:
        self._extraction_payload = extraction_payload
        self._reply = reply
        self._route = route

    def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        if "information extraction engine" in system.lower():
            return self._extraction_payload
        if "routing classifier" in system.lower():
            return self._route or "extract"
        return self._reply


_PAYLOAD = json.dumps({
    "entities": [{"name": "Acme Corp", "type": "organization", "confidence": 0.9}],
    "relationships": [],
})


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

    from agents.graph import build_graph
    from app.dependencies import get_agent_graph
    from app.main import app

    graph_id = f"test-{uuid.uuid4().hex[:8]}"
    fake_llm = FakeLLM(_PAYLOAD, reply="Extracted Acme Corp.")
    app.dependency_overrides[get_agent_graph] = lambda: build_graph(neo4j, graphdb, fake_llm, settings)

    with TestClient(app) as test_client:
        yield test_client, graph_id

    app.dependency_overrides.clear()
    neo4j.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)
    neo4j.run("MATCH (h:IngestEvent {graphId: $gid}) DETACH DELETE h", gid=graph_id)
    neo4j.close()
    graphdb.close()


def test_agent_endpoint_extracts_reasons_and_responds(client_and_graph):
    client, graph_id = client_and_graph

    resp = client.post(f"/agent/{graph_id}", json={"text": "Acme Corp filed a report."})

    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == "Extracted Acme Corp."
    assert body["entitiesExtracted"] == 1

    # Real graph write, not just an LLM echo -- a later /graph read sees it.
    graph = client.get(f"/graph/{graph_id}").json()
    assert any(n["label"] == "Acme Corp" for n in graph["nodes"])


def test_agent_endpoint_recall_intent_searches_real_chat_history(client_and_graph):
    """The memory_agent node (7th of the originally-sketched 7 agent nodes)
    reachable end-to-end via the real HTTP endpoint, not just the graph unit
    tests."""
    client, graph_id = client_and_graph
    from app.dependencies import get_agent_graph
    from app.main import app
    from services import chat_history_service

    settings = get_settings()
    neo4j = Neo4jClient(settings)
    chat_history_service.append_message(
        neo4j, graph_id=graph_id, session_id=f"{graph_id}:default",
        message_id="m1", role="user", content="Who regulates Credit Suisse?",
    )

    graphdb = GraphDBClient(settings)
    fake_llm = FakeLLM(_PAYLOAD, reply="You previously asked about Credit Suisse.", route="recall")
    from agents.graph import build_graph
    app.dependency_overrides[get_agent_graph] = lambda: build_graph(neo4j, graphdb, fake_llm, settings)

    try:
        resp = client.post(f"/agent/{graph_id}", json={"text": "What did I previously ask about Credit Suisse?"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["reply"] == "You previously asked about Credit Suisse."
        assert len(body["memoryHits"]) == 1
        assert "Credit Suisse" in body["memoryHits"][0]
    finally:
        neo4j.run("MATCH (s:ChatSession {graphId: $gid})-[:HAS_MESSAGE]->(m:ChatMessage) DETACH DELETE m", gid=graph_id)
        neo4j.run("MATCH (s:ChatSession {graphId: $gid}) DETACH DELETE s", gid=graph_id)
        neo4j.close()
        graphdb.close()
