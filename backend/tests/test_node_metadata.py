"""Integration tests for node metadata updates (salience, properties, note) --
the Construct tab's Node Inspector editing capability. Properties are a
generic key-value bag (not hardcoded ISIN/LEI/jurisdiction/etc, since those
are FIBO-specific and this product is domain-agnostic)."""

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


def _seed(client: Neo4jClient, graph_id: str) -> None:
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="e1", label="A", type_="T", source_doc="d", extraction_confidence=1.0)


def test_update_salience(neo4j):
    client, graph_id = neo4j
    _seed(client, graph_id)

    graph_service.update_entity_metadata(client, graph_id=graph_id, entity_id="e1", salience=1.8)

    result = graph_service.get_graph(client, graph_id)
    assert result.nodes[0].salience == 1.8


def test_update_properties_and_note(neo4j):
    client, graph_id = neo4j
    _seed(client, graph_id)

    graph_service.update_entity_metadata(
        client, graph_id=graph_id, entity_id="e1",
        properties={"sector": "Banking", "rating": "A"}, note="Watch this one.",
    )

    result = graph_service.get_graph(client, graph_id)
    node = result.nodes[0]
    assert node.properties == {"sector": "Banking", "rating": "A"}
    assert node.note == "Watch this one."


def test_partial_update_leaves_other_fields_unchanged(neo4j):
    client, graph_id = neo4j
    _seed(client, graph_id)
    graph_service.update_entity_metadata(client, graph_id=graph_id, entity_id="e1", salience=1.5)

    graph_service.update_entity_metadata(client, graph_id=graph_id, entity_id="e1", note="just a note")

    result = graph_service.get_graph(client, graph_id)
    node = result.nodes[0]
    assert node.salience == 1.5
    assert node.note == "just a note"
