"""Verifies services/community_service.py's migration off Neo4j GDS onto the
networkx-based analytics engine (PLAN: plans/analytical-engine.md Slice 3).
Separate file from test_community_service.py, which is asserted to pass
UNMODIFIED as this migration's contract-preservation check -- this file only
adds the new "no GDS Cypher issued" assertion the migration itself needs.
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
    except Exception:
        pytest.skip("Neo4j not reachable")
    graph_id = f"test-{uuid.uuid4().hex[:8]}"
    yield client, graph_id
    client.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)
    client.close()


def test_detect_communities_issues_no_gds_cypher(neo4j):
    client, graph_id = neo4j
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="a1", label="A", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="a2", label="B", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(client, graph_id=graph_id, edge_id="e1", source_id="a1", target_id="a2", type_="owns", weight=1.0)

    issued_queries: list[str] = []
    original_run = client.run

    def spying_run(cypher, **params):
        issued_queries.append(cypher)
        return original_run(cypher, **params)

    client.run = spying_run
    try:
        community_service.detect_communities(client, graph_id)
    finally:
        client.run = original_run

    assert not any("gds." in q.lower() for q in issued_queries), issued_queries
