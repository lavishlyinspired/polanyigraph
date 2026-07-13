"""Integration tests for chat session memory against live Neo4j.

PLAN.md §20 item 4: POST /chat was stateless -- every call rebuilt the system
prompt from scratch with no memory of prior turns. This gives each session a
real, ordered message history (mirrors Zep's memory.add/memory.get).
"""

from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from db.neo4j_client import Neo4jClient
from services import chat_history_service


@pytest.fixture
def neo4j():
    client = Neo4jClient(get_settings())
    try:
        client.verify()
    except Exception:
        pytest.skip("Neo4j not reachable")
    graph_id = f"test-{uuid.uuid4().hex[:8]}"
    yield client, graph_id
    client.run("MATCH (s:ChatSession {graphId: $gid})-[:HAS_MESSAGE]->(m:ChatMessage) DETACH DELETE m", gid=graph_id)
    client.run("MATCH (s:ChatSession {graphId: $gid}) DETACH DELETE s", gid=graph_id)
    client.close()


def test_append_and_read_messages_in_order(neo4j):
    client, graph_id = neo4j

    chat_history_service.append_message(
        client, graph_id=graph_id, session_id="s1", message_id="m1", role="user", content="Who regulates Acme?"
    )
    chat_history_service.append_message(
        client, graph_id=graph_id, session_id="s1", message_id="m2", role="assistant", content="FINMA does."
    )

    messages = chat_history_service.get_recent_messages(client, graph_id=graph_id, session_id="s1")

    assert [m.role for m in messages] == ["user", "assistant"]
    assert [m.content for m in messages] == ["Who regulates Acme?", "FINMA does."]


def test_get_recent_messages_respects_limit_and_order(neo4j):
    client, graph_id = neo4j
    for i in range(5):
        chat_history_service.append_message(
            client, graph_id=graph_id, session_id="s1", message_id=f"m{i}", role="user", content=f"msg {i}"
        )

    messages = chat_history_service.get_recent_messages(client, graph_id=graph_id, session_id="s1", limit=2)

    # Most recent 2, in chronological order.
    assert [m.content for m in messages] == ["msg 3", "msg 4"]


def test_sessions_are_scoped_per_graph(neo4j):
    client, graph_id = neo4j
    other_graph_id = f"{graph_id}-other"

    chat_history_service.append_message(client, graph_id=graph_id, session_id="s1", message_id="m1", role="user", content="mine")
    chat_history_service.append_message(client, graph_id=other_graph_id, session_id="s1", message_id="m2", role="user", content="not mine")

    try:
        messages = chat_history_service.get_recent_messages(client, graph_id=graph_id, session_id="s1")
        assert [m.content for m in messages] == ["mine"]
    finally:
        client.run("MATCH (s:ChatSession {graphId: $gid})-[:HAS_MESSAGE]->(m:ChatMessage) DETACH DELETE m", gid=other_graph_id)
        client.run("MATCH (s:ChatSession {graphId: $gid}) DETACH DELETE s", gid=other_graph_id)


def test_empty_session_has_no_history(neo4j):
    client, graph_id = neo4j
    assert chat_history_service.get_recent_messages(client, graph_id=graph_id, session_id="no-such-session") == []
