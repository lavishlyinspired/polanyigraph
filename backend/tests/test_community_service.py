"""Integration tests for services/community_service.py against live Neo4j +
GDS (PLAN.md §20 item 5). Skips cleanly if the GDS plugin isn't installed --
same pattern as the rest of this repo's real-service tests (no mocking the
store itself).
"""

from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from db.neo4j_client import Neo4jClient
from services import community_service, graph_service


@pytest.fixture
def neo4j():
    client = Neo4jClient(get_settings())
    try:
        client.verify()
        client.run("RETURN gds.version() AS version")
    except Exception:
        pytest.skip("Neo4j/GDS not reachable")
    graph_id = f"test-{uuid.uuid4().hex[:8]}"
    yield client, graph_id
    client.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)
    client.close()


def _two_clusters(client, graph_id: str) -> None:
    # Cluster A: a densely-connected triangle.
    for eid, label in [("a1", "Acme Corp"), ("a2", "Acme Holdings"), ("a3", "Acme Ventures")]:
        graph_service.upsert_entity(client, graph_id=graph_id, entity_id=eid, label=label, type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(client, graph_id=graph_id, edge_id="e-a1a2", source_id="a1", target_id="a2", type_="owns", weight=1.0)
    graph_service.upsert_relationship(client, graph_id=graph_id, edge_id="e-a2a3", source_id="a2", target_id="a3", type_="owns", weight=1.0)
    graph_service.upsert_relationship(client, graph_id=graph_id, edge_id="e-a3a1", source_id="a3", target_id="a1", type_="owns", weight=1.0)

    # Cluster B: a separate densely-connected triangle, no edges to cluster A.
    for eid, label in [("b1", "Beta Bank"), ("b2", "Beta Trust"), ("b3", "Beta Capital")]:
        graph_service.upsert_entity(client, graph_id=graph_id, entity_id=eid, label=label, type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(client, graph_id=graph_id, edge_id="e-b1b2", source_id="b1", target_id="b2", type_="owns", weight=1.0)
    graph_service.upsert_relationship(client, graph_id=graph_id, edge_id="e-b2b3", source_id="b2", target_id="b3", type_="owns", weight=1.0)
    graph_service.upsert_relationship(client, graph_id=graph_id, edge_id="e-b3b1", source_id="b3", target_id="b1", type_="owns", weight=1.0)


def test_detect_communities_separates_two_disconnected_clusters(neo4j):
    client, graph_id = neo4j
    _two_clusters(client, graph_id)

    members = community_service.detect_communities(client, graph_id)

    assert len(members) == 6
    by_entity = {m.entity_id: m.community_id for m in members}
    a_communities = {by_entity["a1"], by_entity["a2"], by_entity["a3"]}
    b_communities = {by_entity["b1"], by_entity["b2"], by_entity["b3"]}
    assert len(a_communities) == 1  # all of cluster A in the same community
    assert len(b_communities) == 1  # all of cluster B in the same community
    assert a_communities != b_communities  # and the two clusters are distinct


def test_detect_communities_writes_community_id_onto_entities(neo4j):
    client, graph_id = neo4j
    _two_clusters(client, graph_id)

    community_service.detect_communities(client, graph_id)

    record = graph_service.get_graph(client, graph_id)
    a1 = next(n for n in record.nodes if n.id == "a1")
    assert a1.community_id is not None


def test_get_communities_reads_without_recomputing(neo4j):
    client, graph_id = neo4j
    _two_clusters(client, graph_id)
    community_service.detect_communities(client, graph_id)

    members = community_service.get_communities(client, graph_id)

    assert len(members) == 6


def test_empty_graph_has_no_communities(neo4j):
    client, graph_id = neo4j
    assert community_service.detect_communities(client, graph_id) == []
    assert community_service.get_communities(client, graph_id) == []


def test_communities_are_scoped_per_graph(neo4j):
    client, graph_id = neo4j
    other_graph_id = f"{graph_id}-other"
    _two_clusters(client, graph_id)
    graph_service.upsert_entity(client, graph_id=other_graph_id, entity_id="x1", label="Unrelated", type_="organization", source_doc="d", extraction_confidence=1.0)

    try:
        community_service.detect_communities(client, other_graph_id)
        members = community_service.get_communities(client, graph_id)
        assert {m.entity_id for m in members}.isdisjoint({"x1"})
    finally:
        client.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=other_graph_id)
