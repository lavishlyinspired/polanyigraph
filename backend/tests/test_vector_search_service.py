"""Integration tests for services/vector_search_service.py -- Option A
(GRAPHITI_INTEGRATION_PLAN.md §4) native semantic search, replacing
memory_service's plain CONTAINS matching. Uses the real embedding client
(a fast NVIDIA call, already confirmed live) since faking vectors would
trivialize the one thing worth testing here: that semantically related text
actually ranks above unrelated text, not just that the Cypher runs.
"""

from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from app.dependencies import get_embedder
from db.neo4j_client import Neo4jClient
from services import vector_search_service


@pytest.fixture
def neo4j():
    client = Neo4jClient(get_settings())
    try:
        client.verify()
    except Exception:
        pytest.skip("Neo4j not reachable")
    yield client
    client.close()


@pytest.fixture
def embedder():
    e = get_embedder()
    try:
        e.verify()
    except Exception:
        pytest.skip("Embedding endpoint not reachable")
    return e


@pytest.fixture
def graph_id(neo4j):
    gid = f"test-{uuid.uuid4().hex[:8]}"
    yield gid
    # Real bug found 2026-07-13: this fixture never cleaned up, unlike every
    # other test fixture in this codebase -- leaked Entity/ChatSession/
    # ChatMessage nodes with real summaryEmbedding vectors accumulated in
    # the shared dev Neo4j across every session's test runs, degrading the
    # ANN vector index's ability to find genuinely fresh nodes (confirmed:
    # 54 leaked entities found, all scoring identically in queryNodes,
    # crowding out real results).
    neo4j.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=gid)
    # DETACH DELETE on ChatSession alone orphans its ChatMessage children
    # (confirmed live: this exact mistake, made once cleaning up the leaked
    # pollution this bug caused, left 680 orphaned ChatMessage nodes behind)
    # -- delete the messages first, then the session.
    neo4j.run("MATCH (s:ChatSession {graphId: $gid})-[:HAS_MESSAGE]->(m:ChatMessage) DETACH DELETE m", gid=gid)
    neo4j.run("MATCH (s:ChatSession {graphId: $gid}) DETACH DELETE s", gid=gid)


def test_ensure_indexes_is_idempotent(neo4j):
    vector_search_service.ensure_indexes(neo4j, dimensions=1024)
    vector_search_service.ensure_indexes(neo4j, dimensions=1024)  # must not raise on rerun


def test_index_and_search_entity_summary_ranks_semantic_match_first(neo4j, embedder, graph_id):
    vector_search_service.ensure_indexes(neo4j, dimensions=embedder.dimensions)
    neo4j.run(
        "CREATE (e:Entity {id: $id, graphId: $gid, label: 'Deutsche Bank AG', type: 'commercial bank'})",
        id=f"{graph_id}:e1", gid=graph_id,
    )
    neo4j.run(
        "CREATE (e:Entity {id: $id, graphId: $gid, label: 'Zurich', type: 'business center'})",
        id=f"{graph_id}:e2", gid=graph_id,
    )
    vector_search_service.index_entity_summary(
        neo4j, embedder, graph_id=graph_id, entity_id=f"{graph_id}:e1",
        summary="A large German commercial bank headquartered in Frankfurt, regulated by BaFin.",
    )
    vector_search_service.index_entity_summary(
        neo4j, embedder, graph_id=graph_id, entity_id=f"{graph_id}:e2",
        summary="A city in Switzerland known as a global financial center.",
    )

    hits = vector_search_service.search_entities(neo4j, embedder, graph_id=graph_id, query="German banking regulation", limit=5)

    assert len(hits) >= 1
    assert hits[0].id == f"{graph_id}:e1"


def test_index_and_search_chat_message(neo4j, embedder, graph_id):
    vector_search_service.ensure_indexes(neo4j, dimensions=embedder.dimensions)
    session_id = f"{graph_id}:default"
    neo4j.run(
        "MERGE (s:ChatSession {id: $sid, graphId: $gid}) "
        "CREATE (m:ChatMessage {id: $mid, role: 'user', content: $content, seq: 0, createdAt: datetime()}) "
        "MERGE (s)-[:HAS_MESSAGE]->(m)",
        sid=session_id, gid=graph_id, mid=f"{session_id}:m1",
        content="My supplier is Bosch and they ship gearboxes.",
    )

    vector_search_service.index_chat_message(
        neo4j, embedder, message_id=f"{session_id}:m1", content="My supplier is Bosch and they ship gearboxes.",
    )

    hits = vector_search_service.search_chat_messages(neo4j, embedder, graph_id=graph_id, query="who is the parts supplier", limit=5)

    assert any(h.id == f"{session_id}:m1" for h in hits)
