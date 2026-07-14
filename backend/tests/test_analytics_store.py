"""Integration tests for analytics/store.py's Neo4jGraphStore against live Neo4j."""

from __future__ import annotations

import uuid

import pytest

from analytics.projection import NamedProjection
from analytics.store import Neo4jGraphStore
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


def test_write_scores_sets_property_on_entity_nodes(neo4j):
    client, graph_id = neo4j
    graph_service.upsert_entity(
        client, graph_id=graph_id, entity_id="a1", label="Acme Corp", type_="organization",
        source_doc="d", extraction_confidence=1.0,
    )
    projection = NamedProjection.create(client, name="p1", graph_id=graph_id)
    store = Neo4jGraphStore(client)

    store.write_scores(projection, "centralityScore", {"a1": 0.75})

    rows = client.run(
        "MATCH (e:Entity {id: $id, graphId: $gid}) RETURN e.centralityScore AS score",
        id="a1", gid=graph_id,
    )
    assert rows[0]["score"] == 0.75


def test_write_scores_only_touches_nodes_in_the_scores_dict(neo4j):
    client, graph_id = neo4j
    for eid in ("a1", "a2"):
        graph_service.upsert_entity(
            client, graph_id=graph_id, entity_id=eid, label=eid, type_="organization",
            source_doc="d", extraction_confidence=1.0,
        )
    projection = NamedProjection.create(client, name="p1", graph_id=graph_id)
    store = Neo4jGraphStore(client)

    store.write_scores(projection, "centralityScore", {"a1": 0.5})

    rows = client.run(
        "MATCH (e:Entity {id: $id, graphId: $gid}) RETURN e.centralityScore AS score",
        id="a2", gid=graph_id,
    )
    assert rows[0]["score"] is None
