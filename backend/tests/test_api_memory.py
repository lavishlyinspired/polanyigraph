"""REST surface for cross-source memory search + preferences (PLAN.md §9),
so the MemoryInspector frontend component can search real chat history +
entity summaries and manage real preferences the same way
mcp_memory_server.py does for MCP clients -- both wrap
services/memory_service.py and services/preferences_store.py.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from db.neo4j_client import Neo4jClient


def _neo4j_reachable() -> bool:
    client = Neo4jClient(get_settings())
    try:
        client.verify()
        return True
    except Exception:
        return False
    finally:
        client.close()


def test_search_memory_finds_real_seeded_chat_history():
    if not _neo4j_reachable():
        return
    graph_id = f"test-memory-{uuid.uuid4().hex[:8]}"
    neo4j = Neo4jClient(get_settings())
    session_id = f"session-{uuid.uuid4().hex[:8]}"
    neo4j.run(
        """
        MERGE (s:ChatSession {id: $session_id, graphId: $graph_id})
        CREATE (s)-[:HAS_MESSAGE]->(m:ChatMessage {
            id: $msg_id, content: 'We discussed Credit Suisse bond covenants.',
            seq: 0, createdAt: datetime()
        })
        """,
        session_id=session_id, graph_id=graph_id, msg_id=f"msg-{uuid.uuid4().hex[:8]}",
    )
    try:
        with TestClient(app) as client:
            resp = client.post(f"/memory/{graph_id}/search", json={"query": "Credit Suisse"})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["hits"]) == 1
        assert body["hits"][0]["kind"] == "chat_message"
        assert "Credit Suisse" in body["hits"][0]["text"]
    finally:
        neo4j.run("MATCH (s:ChatSession {id: $session_id})-[:HAS_MESSAGE]->(m:ChatMessage) DETACH DELETE m", session_id=session_id)
        neo4j.run("MATCH (s:ChatSession {id: $session_id}) DETACH DELETE s", session_id=session_id)
        neo4j.close()


def test_search_memory_returns_empty_for_no_matches():
    if not _neo4j_reachable():
        return
    with TestClient(app) as client:
        resp = client.post("/memory/no-such-graph/search", json={"query": "nonexistent-term-xyz"})
    assert resp.status_code == 200
    assert resp.json()["hits"] == []


def test_preferences_roundtrip_through_real_neo4j():
    if not _neo4j_reachable():
        return
    key = f"test-pref-{uuid.uuid4().hex[:8]}"
    try:
        with TestClient(app) as client:
            save_resp = client.put(f"/memory/preferences/{key}", json={"value": "dark-mode"})
            assert save_resp.status_code == 200

            list_resp = client.get("/memory/preferences")
            keys = {p["key"] for p in list_resp.json()["preferences"]}
            assert key in keys

            delete_resp = client.delete(f"/memory/preferences/{key}")
            assert delete_resp.status_code == 200

            list_resp_after = client.get("/memory/preferences")
            keys_after = {p["key"] for p in list_resp_after.json()["preferences"]}
            assert key not in keys_after
    finally:
        neo4j = Neo4jClient(get_settings())
        neo4j.run("MATCH (p:Preference {key: $key}) DETACH DELETE p", key=key)
        neo4j.close()
