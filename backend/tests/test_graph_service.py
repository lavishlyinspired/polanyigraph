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
