"""Integration test: list all graphs (for the UI's graph switcher)."""

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
    client.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)
    client.run("MATCH (h:IngestEvent {graphId: $gid}) DETACH DELETE h", gid=graph_id)
    client.close()


def test_list_graphs_includes_seeded_graph_with_counts(neo4j):
    client, graph_id = neo4j
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="e1", label="A", type_="T", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="e2", label="B", type_="T", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(client, graph_id=graph_id, edge_id="r1", source_id="e1", target_id="e2", type_="R", weight=1.0)
    history_service.record_ingest_event(client, graph_id=graph_id, event_id="evt-1", text="t", entity_count=2, relationship_count=1, dropped_count=0)

    graphs = graph_service.list_graphs(client)

    match = next(g for g in graphs if g.graph_id == graph_id)
    assert match.node_count == 2
    assert match.edge_count == 1
    assert match.last_ingest_at is not None


def test_list_graphs_excludes_unrelated_graphs(neo4j):
    client, graph_id = neo4j
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="e1", label="A", type_="T", source_doc="d", extraction_confidence=1.0)

    graphs = graph_service.list_graphs(client)

    assert all(g.node_count > 0 or g.last_ingest_at for g in graphs)
