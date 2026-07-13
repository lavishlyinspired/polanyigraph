"""Integration tests for real cross-source memory search against live Neo4j.

Backs the memory_agent LangGraph node (PLAN.md §2, 7th of the originally-
sketched 7 agent nodes) and the Memory MCP server's search_memory tool.
Searches real, already-persisted data -- chat session history
(services/chat_history_service.py) and entity summaries
(services/graph_service.py's evolving-summary field) -- not a new store.
"""

from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from app.dependencies import get_embedder
from db.neo4j_client import Neo4jClient
from services import chat_history_service, graph_service, memory_config_service, memory_service, vector_search_service


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
    client.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)
    client.close()


def test_search_memory_finds_matching_chat_messages(neo4j):
    client, graph_id = neo4j
    chat_history_service.append_message(
        client, graph_id=graph_id, session_id="s1", message_id="m1", role="user", content="Who regulates FINMA?"
    )
    chat_history_service.append_message(
        client, graph_id=graph_id, session_id="s1", message_id="m2", role="assistant", content="The weather is nice."
    )

    hits = memory_service.search_memory(client, graph_id=graph_id, query="regulates")

    assert len(hits) == 1
    assert hits[0].kind == "chat_message"
    assert "FINMA" in hits[0].text


def test_search_memory_finds_matching_entity_summaries(neo4j):
    client, graph_id = neo4j
    graph_service.upsert_entity(
        client, graph_id=graph_id, entity_id="e1", label="Credit Suisse",
        type_="organization", source_doc="d", extraction_confidence=1.0,
    )
    graph_service.update_entity_summary(
        client, graph_id=graph_id, entity_id="e1",
        summary="Credit Suisse was acquired by UBS Group in 2023.",
    )

    hits = memory_service.search_memory(client, graph_id=graph_id, query="acquired")

    assert len(hits) == 1
    assert hits[0].kind == "entity_summary"
    assert "UBS Group" in hits[0].text


def test_search_memory_is_case_insensitive_and_scoped_per_graph(neo4j):
    client, graph_id = neo4j
    other_graph_id = f"{graph_id}-other"
    chat_history_service.append_message(
        client, graph_id=graph_id, session_id="s1", message_id="m1", role="user", content="ACME Corp is regulated"
    )
    chat_history_service.append_message(
        client, graph_id=other_graph_id, session_id="s1", message_id="m2", role="user", content="acme corp elsewhere"
    )

    try:
        hits = memory_service.search_memory(client, graph_id=graph_id, query="acme")
        assert len(hits) == 1
        assert hits[0].text == "ACME Corp is regulated"
    finally:
        client.run("MATCH (s:ChatSession {graphId: $gid})-[:HAS_MESSAGE]->(m:ChatMessage) DETACH DELETE m", gid=other_graph_id)
        client.run("MATCH (s:ChatSession {graphId: $gid}) DETACH DELETE s", gid=other_graph_id)


def test_search_memory_respects_limit_across_combined_sources(neo4j):
    client, graph_id = neo4j
    for i in range(3):
        chat_history_service.append_message(
            client, graph_id=graph_id, session_id="s1", message_id=f"m{i}", role="user", content=f"match {i}"
        )

    hits = memory_service.search_memory(client, graph_id=graph_id, query="match", limit=2)

    assert len(hits) == 2


def test_search_memory_returns_empty_for_no_matches(neo4j):
    client, graph_id = neo4j
    assert memory_service.search_memory(client, graph_id=graph_id, query="nonexistent") == []


def test_search_memory_with_embedder_finds_semantic_match_with_no_literal_overlap(neo4j):
    """GRAPHITI_INTEGRATION_PLAN.md §4 Option A: passing an embedder upgrades
    search from plain CONTAINS to hybrid vector+text -- a query with zero
    literal word overlap should still surface a semantically related summary."""
    client, graph_id = neo4j
    embedder = get_embedder()
    try:
        embedder.verify()
    except Exception:
        pytest.skip("Embedding endpoint not reachable")
    vector_search_service.ensure_indexes(client, dimensions=embedder.dimensions)

    graph_service.upsert_entity(
        client, graph_id=graph_id, entity_id="e1", label="Deutsche Bank AG",
        type_="organization", source_doc="d", extraction_confidence=1.0,
    )
    graph_service.update_entity_summary(
        client, graph_id=graph_id, entity_id="e1",
        summary="A large German commercial bank headquartered in Frankfurt, regulated by BaFin.",
    )
    vector_search_service.index_entity_summary(
        client, embedder, graph_id=graph_id, entity_id="e1",
        summary="A large German commercial bank headquartered in Frankfurt, regulated by BaFin.",
    )

    hits_without_embedder = memory_service.search_memory(client, graph_id=graph_id, query="German banking oversight")
    hits_with_embedder = memory_service.search_memory(client, graph_id=graph_id, query="German banking oversight", embedder=embedder)

    assert hits_without_embedder == []  # no literal substring overlap -- CONTAINS-only finds nothing
    assert any(h.id == "e1" for h in hits_with_embedder)


def test_search_memory_falls_back_to_native_when_graphiti_backend_selected_but_unconfigured(neo4j):
    """GRAPHITI_INTEGRATION_PLAN.md §4: flipping the backend toggle to
    'graphiti' before saving a connection shouldn't silently return nothing
    -- it should fall through to the native path so search keeps working."""
    client, graph_id = neo4j
    try:
        memory_config_service.set_backend(client, "graphiti")
        chat_history_service.append_message(
            client, graph_id=graph_id, session_id="s1", message_id="m1", role="user", content="Who regulates FINMA?",
        )

        hits = memory_service.search_memory(client, graph_id=graph_id, query="regulates", embedder=get_embedder(), settings=get_settings())

        assert len(hits) == 1
        assert hits[0].kind == "chat_message"
    finally:
        memory_config_service.set_backend(client, "native")
