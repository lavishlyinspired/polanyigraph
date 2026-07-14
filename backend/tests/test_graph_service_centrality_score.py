"""Verifies get_graph() surfaces a written-back centralityScore, the same
way it already surfaces communityId (PLAN: plans/analytical-engine.md Slice
9) -- closes a real gap found by browser verification: the analytics engine
could write centralityScore onto :Entity nodes (Slice 1's Neo4jGraphStore),
but get_graph() never read it back, so the frontend could never see it.
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


def test_get_graph_surfaces_a_written_back_centrality_score(neo4j):
    client, graph_id = neo4j
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="a1", label="A", type_="organization", source_doc="d", extraction_confidence=1.0)
    client.run(
        "MATCH (e:Entity {id: $id, graphId: $gid}) SET e.centralityScore = $score",
        id="a1", gid=graph_id, score=0.75,
    )

    record = graph_service.get_graph(client, graph_id)

    node = next(n for n in record.nodes if n.id == "a1")
    assert node.centrality_score == 0.75


def test_get_graph_centrality_score_is_none_when_never_written(neo4j):
    client, graph_id = neo4j
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="a1", label="A", type_="organization", source_doc="d", extraction_confidence=1.0)

    record = graph_service.get_graph(client, graph_id)

    node = next(n for n in record.nodes if n.id == "a1")
    assert node.centrality_score is None
