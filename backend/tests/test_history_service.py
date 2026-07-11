"""Integration tests for ingest history tracking against live Neo4j.

Currently every ingest into a graph writes the same generic sourceDoc label
("pasted-text:{graph_id}") with the actual posted text stored nowhere — so
there's nothing to review. This adds a real, queryable history of what was
posted, when, and what it produced.
"""

from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from db.neo4j_client import Neo4jClient
from services import graph_service, history_service


@pytest.fixture
def neo4j():
    client = Neo4jClient(get_settings())
    try:
        client.verify()
    except Exception:
        pytest.skip("Neo4j not reachable")
    graph_id = f"test-{uuid.uuid4().hex[:8]}"
    yield client, graph_id
    client.run("MATCH (h:IngestEvent {graphId: $gid}) DETACH DELETE h", gid=graph_id)
    client.close()


def test_record_and_list_ingest_event(neo4j):
    client, graph_id = neo4j

    history_service.record_ingest_event(
        client, graph_id=graph_id, event_id="evt-1", text="Deutsche Bank AG issues bonds.",
        entity_count=2, relationship_count=1, dropped_count=0,
    )

    events = history_service.list_ingest_events(client, graph_id)

    assert len(events) == 1
    assert events[0].id == "evt-1"
    assert events[0].text == "Deutsche Bank AG issues bonds."
    assert events[0].entity_count == 2
    assert events[0].relationship_count == 1
    assert events[0].created_at is not None


def test_history_is_ordered_most_recent_first(neo4j):
    client, graph_id = neo4j

    history_service.record_ingest_event(client, graph_id=graph_id, event_id="evt-1", text="first", entity_count=1, relationship_count=0, dropped_count=0)
    history_service.record_ingest_event(client, graph_id=graph_id, event_id="evt-2", text="second", entity_count=1, relationship_count=0, dropped_count=0)

    events = history_service.list_ingest_events(client, graph_id)

    assert [e.id for e in events] == ["evt-2", "evt-1"]


def test_history_is_scoped_per_graph(neo4j):
    client, graph_id = neo4j
    other_graph_id = f"{graph_id}-other"

    history_service.record_ingest_event(client, graph_id=graph_id, event_id="evt-1", text="mine", entity_count=1, relationship_count=0, dropped_count=0)
    history_service.record_ingest_event(client, graph_id=other_graph_id, event_id="evt-2", text="not mine", entity_count=1, relationship_count=0, dropped_count=0)

    try:
        events = history_service.list_ingest_events(client, graph_id)
        assert [e.id for e in events] == ["evt-1"]
    finally:
        client.run("MATCH (h:IngestEvent {graphId: $gid}) DETACH DELETE h", gid=other_graph_id)


def test_empty_graph_has_no_history(neo4j):
    client, graph_id = neo4j
    assert history_service.list_ingest_events(client, graph_id) == []


def test_record_ingest_event_links_produced_entities(neo4j):
    """PLAN.md §20 item 1: provenance is a graph traversal, not a sourceDoc string."""
    client, graph_id = neo4j
    entity_id = f"{graph_id}:e1"
    try:
        graph_service.upsert_entity(
            client, graph_id=graph_id, entity_id=entity_id, label="Acme Corp", type_="BusinessEntity",
            source_doc="doc-1", extraction_confidence=0.9,
        )

        history_service.record_ingest_event(
            client, graph_id=graph_id, event_id="evt-1", text="Acme Corp exists.",
            entity_count=1, relationship_count=0, dropped_count=0, entity_ids=[entity_id],
        )

        produced = history_service.get_produced_entity_ids(client, graph_id=graph_id, event_id="evt-1")
        assert produced == [entity_id]
    finally:
        client.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)


def test_record_ingest_event_with_no_entities_is_fine(neo4j):
    client, graph_id = neo4j
    history_service.record_ingest_event(
        client, graph_id=graph_id, event_id="evt-1", text="nothing extracted",
        entity_count=0, relationship_count=0, dropped_count=1,
    )
    assert history_service.get_produced_entity_ids(client, graph_id=graph_id, event_id="evt-1") == []
