"""Unit tests for analytics/projection.py's build_graph (pure, no DB) and
integration tests for NamedProjection against live Neo4j.

build_graph maps GraphNodeRecord/GraphEdgeRecord directly onto a
networkx.DiGraph's node/edge attributes -- no third node/edge model (see
plans/analytical-engine.md's "Data model mapping" section). This test
asserts every field survives the mapping unchanged, since later slices
(activation_patterns, community migration) depend on that being true.
"""

from __future__ import annotations

import uuid

import networkx as nx
import pytest

from analytics.projection import NamedProjection, build_graph
from app.config import get_settings
from db.neo4j_client import Neo4jClient
from services import graph_service
from services.graph_service import GraphEdgeRecord, GraphNodeRecord


def test_build_graph_returns_a_directed_graph():
    graph = build_graph([], [])
    assert isinstance(graph, nx.DiGraph)


def test_build_graph_maps_every_node_field_onto_node_attributes():
    node = GraphNodeRecord(
        id="e1",
        label="Acme Corp",
        type="organization",
        activation=0.42,
        derived=True,
        salience=0.9,
        properties={"isin": "US1234567890"},
        community_id=3,
    )

    graph = build_graph([node], [])

    assert set(graph.nodes) == {"e1"}
    attrs = graph.nodes["e1"]
    assert attrs["label"] == "Acme Corp"
    assert attrs["type"] == "organization"
    assert attrs["activation"] == 0.42
    assert attrs["derived"] is True
    assert attrs["salience"] == 0.9
    assert attrs["community_id"] == 3
    assert attrs["isin"] == "US1234567890"  # arbitrary properties dict flattened in


def test_build_graph_maps_edge_fields_and_preserves_direction():
    nodes = [
        GraphNodeRecord(id="a", label="A", type="t"),
        GraphNodeRecord(id="b", label="B", type="t"),
    ]
    edge = GraphEdgeRecord(id="e-ab", source="a", target="b", type="owns", weight=2.5)

    graph = build_graph(nodes, [edge])

    assert graph.has_edge("a", "b")
    assert not graph.has_edge("b", "a")
    attrs = graph.edges["a", "b"]
    assert attrs["id"] == "e-ab"
    assert attrs["type"] == "owns"
    assert attrs["weight"] == 2.5


def test_build_graph_defaults_survive_for_a_minimal_node():
    node = GraphNodeRecord(id="x", label="X", type="t")

    graph = build_graph([node], [])

    attrs = graph.nodes["x"]
    assert attrs["activation"] is None
    assert attrs["derived"] is False
    assert attrs["salience"] == 1.0
    assert attrs["community_id"] is None


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


def _seed_triangle(client: Neo4jClient, graph_id: str) -> None:
    for eid, label in [("a1", "Acme Corp"), ("a2", "Acme Holdings"), ("a3", "Acme Ventures")]:
        graph_service.upsert_entity(
            client, graph_id=graph_id, entity_id=eid, label=label, type_="organization",
            source_doc="d", extraction_confidence=1.0,
        )
    graph_service.upsert_relationship(client, graph_id=graph_id, edge_id="e-a1a2", source_id="a1", target_id="a2", type_="owns", weight=1.0)
    graph_service.upsert_relationship(client, graph_id=graph_id, edge_id="e-a2a3", source_id="a2", target_id="a3", type_="owns", weight=1.0)


def test_named_projection_materializes_graphid_scoped_subgraph_from_neo4j(neo4j):
    client, graph_id = neo4j
    _seed_triangle(client, graph_id)

    projection = NamedProjection.create(client, name="p1", graph_id=graph_id)

    assert projection.name == "p1"
    assert set(projection.graph.nodes) == {"a1", "a2", "a3"}
    assert projection.graph.has_edge("a1", "a2")
    assert projection.graph.has_edge("a2", "a3")


def test_named_projection_is_scoped_to_its_graph_id_only(neo4j):
    client, graph_id = neo4j
    _seed_triangle(client, graph_id)
    other_graph_id = f"test-{uuid.uuid4().hex[:8]}"
    graph_service.upsert_entity(
        client, graph_id=other_graph_id, entity_id="other", label="Other", type_="organization",
        source_doc="d", extraction_confidence=1.0,
    )
    try:
        projection = NamedProjection.create(client, name="p2", graph_id=graph_id)
        assert "other" not in projection.graph.nodes
    finally:
        client.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=other_graph_id)
