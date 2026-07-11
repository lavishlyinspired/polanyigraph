"""Integration tests for services/graph_service.py against live Neo4j.

Uses a random graph_id per test so runs are isolated and self-cleaning; skips
cleanly when Neo4j Desktop isn't running (no mocking the store itself).
"""

from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from db.neo4j_client import Neo4jClient
from services import graph_service


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
    client.close()


def test_upsert_and_read_round_trip(neo4j):
    client, graph_id = neo4j

    graph_service.upsert_entity(
        client, graph_id=graph_id, entity_id="e1", label="Acme Corp", type_="BusinessEntity",
        source_doc="doc-1", extraction_confidence=0.9,
    )
    graph_service.upsert_entity(
        client, graph_id=graph_id, entity_id="e2", label="Series A Stock", type_="Security",
        source_doc="doc-1", extraction_confidence=0.85,
    )
    graph_service.upsert_relationship(
        client, graph_id=graph_id, edge_id="r1", source_id="e1", target_id="e2",
        type_="issuedBy", weight=1.0,
    )

    result = graph_service.get_graph(client, graph_id)

    assert {n.id for n in result.nodes} == {"e1", "e2"}
    assert result.edges[0].source == "e1"
    assert result.edges[0].target == "e2"
    acme = next(n for n in result.nodes if n.id == "e1")
    assert acme.label == "Acme Corp"
    assert acme.type == "BusinessEntity"
    assert acme.source_doc == "doc-1"


def test_upsert_entity_is_idempotent(neo4j):
    client, graph_id = neo4j

    for _ in range(3):
        graph_service.upsert_entity(
            client, graph_id=graph_id, entity_id="dup", label="Same", type_="T",
            source_doc="doc", extraction_confidence=1.0,
        )

    result = graph_service.get_graph(client, graph_id)
    assert len(result.nodes) == 1


def test_empty_graph_returns_empty_lists(neo4j):
    client, graph_id = neo4j
    result = graph_service.get_graph(client, graph_id)
    assert result.nodes == []
    assert result.edges == []


def test_upsert_relationship_stamps_valid_at_and_provenance(neo4j):
    client, graph_id = neo4j
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="e1", label="Acme", type_="T", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="e2", label="Zurich", type_="T", source_doc="d", extraction_confidence=1.0)

    graph_service.upsert_relationship(
        client, graph_id=graph_id, edge_id="r1", source_id="e1", target_id="e2",
        type_="hasDomicile", weight=1.0, produced_by_event_id="evt-1",
    )

    result = graph_service.get_graph(client, graph_id)
    edge = result.edges[0]
    assert edge.valid_at is not None
    assert edge.invalid_at is None
    assert edge.produced_by_event_id == "evt-1"


def test_upsert_relationship_invalidates_prior_edge_to_different_target(neo4j):
    """PLAN.md §20 item 2: a contradicting fact invalidates the old edge instead of
    silently coexisting forever with no signal about which is current."""
    client, graph_id = neo4j
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="acme", label="Acme", type_="T", source_doc="d1", extraction_confidence=1.0)
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="zurich", label="Zurich", type_="T", source_doc="d1", extraction_confidence=1.0)
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="geneva", label="Geneva", type_="T", source_doc="d2", extraction_confidence=1.0)

    graph_service.upsert_relationship(
        client, graph_id=graph_id, edge_id="r-zurich", source_id="acme", target_id="zurich",
        type_="hasDomicile", weight=0.9, produced_by_event_id="evt-1",
    )
    graph_service.upsert_relationship(
        client, graph_id=graph_id, edge_id="r-geneva", source_id="acme", target_id="geneva",
        type_="hasDomicile", weight=0.9, produced_by_event_id="evt-2",
    )

    # Default read: only the current fact.
    current = graph_service.get_graph(client, graph_id)
    assert len(current.edges) == 1
    assert current.edges[0].target == "geneva"
    assert current.edges[0].invalid_at is None

    # Full history: both, old one invalidated.
    history = graph_service.get_relationship_history(client, graph_id=graph_id, source_id="acme", type_="hasDomicile")
    by_target = {e.target: e for e in history}
    assert len(history) == 2
    assert by_target["zurich"].invalid_at is not None
    assert by_target["geneva"].invalid_at is None


def test_upsert_relationship_same_triple_reingested_does_not_self_invalidate(neo4j):
    client, graph_id = neo4j
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="acme", label="Acme", type_="T", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="zurich", label="Zurich", type_="T", source_doc="d", extraction_confidence=1.0)

    for _ in range(2):
        graph_service.upsert_relationship(
            client, graph_id=graph_id, edge_id="r-zurich", source_id="acme", target_id="zurich",
            type_="hasDomicile", weight=0.9, produced_by_event_id="evt-1",
        )

    result = graph_service.get_graph(client, graph_id)
    assert len(result.edges) == 1
    assert result.edges[0].invalid_at is None


def test_entity_summary_defaults_empty_then_can_be_updated(neo4j):
    client, graph_id = neo4j
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="e1", label="Acme", type_="T", source_doc="d", extraction_confidence=1.0)

    assert graph_service.get_entity_summary(client, graph_id=graph_id, entity_id="e1") == ""

    graph_service.update_entity_summary(client, graph_id=graph_id, entity_id="e1", summary="Acme is a business entity mentioned in doc 1.")

    assert graph_service.get_entity_summary(client, graph_id=graph_id, entity_id="e1") == "Acme is a business entity mentioned in doc 1."
    node = graph_service.get_graph(client, graph_id).nodes[0]
    assert node.summary == "Acme is a business entity mentioned in doc 1."


def test_get_entities_and_edges_for_reasoning_maps_types(neo4j):
    client, graph_id = neo4j
    graph_service.upsert_entity(
        client, graph_id=graph_id, entity_id="e1", label="A", type_="T",
        source_doc="doc", extraction_confidence=1.0, salience=0.8,
    )
    graph_service.upsert_entity(
        client, graph_id=graph_id, entity_id="e2", label="B", type_="T",
        source_doc="doc", extraction_confidence=1.0,
    )
    graph_service.upsert_relationship(
        client, graph_id=graph_id, edge_id="r1", source_id="e1", target_id="e2", type_="R", weight=0.5,
    )

    nodes, edges = graph_service.get_entities_and_edges_for_reasoning(client, graph_id)

    node_by_id = {n.id: n for n in nodes}
    assert node_by_id["e1"].type == "T"
    assert node_by_id["e1"].salience == 0.8
    assert edges[0].source == "e1" and edges[0].target == "e2" and edges[0].weight == 0.5
