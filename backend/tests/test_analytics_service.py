"""Unit/integration tests for services/analytics_service.py."""

from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient
from services import analytics_service, graph_service


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


@pytest.fixture
def neo4j_and_graphdb():
    settings = get_settings()
    neo4j = Neo4jClient(settings)
    graphdb = GraphDBClient(settings)
    try:
        neo4j.verify()
        graphdb.verify()
    except Exception:
        pytest.skip("Neo4j/GraphDB not reachable")
    graph_id = f"test-{uuid.uuid4().hex[:8]}"
    yield neo4j, graphdb, settings, graph_id
    neo4j.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)
    neo4j.close()
    graphdb.close()


def test_run_default_analysis_returns_scores_for_a_real_graph(neo4j):
    client, graph_id = neo4j
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="hub", label="Hub", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="leaf", label="Leaf", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(client, graph_id=graph_id, edge_id="e1", source_id="hub", target_id="leaf", type_="owns", weight=1.0)

    scores = analytics_service.run_default_analysis(client, graph_id)

    assert set(scores) == {"hub", "leaf"}


def test_run_default_analysis_on_empty_graph_returns_empty_dict(neo4j):
    client, graph_id = neo4j

    scores = analytics_service.run_default_analysis(client, graph_id)

    assert scores == {}


def test_run_default_analysis_never_registers_a_named_projection(neo4j):
    """Ad hoc agent-turn analysis must not leak into the HTTP API's
    NamedProjection registry (same discipline as community_service.py)."""
    from analytics.projection import NamedProjection

    client, graph_id = neo4j
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="a", label="A", type_="organization", source_doc="d", extraction_confidence=1.0)

    analytics_service.run_default_analysis(client, graph_id)

    assert NamedProjection.get(graph_id) is None


def test_run_default_analysis_with_unknown_algorithm_returns_empty_dict(neo4j):
    client, graph_id = neo4j
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="a", label="A", type_="organization", source_doc="d", extraction_confidence=1.0)

    scores = analytics_service.run_default_analysis(client, graph_id, algorithm="not_a_real_algorithm")

    assert scores == {}


def test_run_default_analysis_without_graphdb_leaves_scores_unweighted(neo4j):
    """Backward-compatible default: a caller that doesn't pass graphdb/
    repository gets today's behavior unchanged (no role weighting)."""
    client, graph_id = neo4j
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="hub", label="Hub", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="rate", label="8.45%", type_="rate of return", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(client, graph_id=graph_id, edge_id="e1", source_id="hub", target_id="rate", type_="reports", weight=1.0)

    scores = analytics_service.run_default_analysis(client, graph_id)

    assert scores["rate"] > 0.0


def test_run_default_analysis_role_weights_noisy_value_entities_when_graphdb_given(neo4j_and_graphdb):
    """The real Phase 1 fix: a "rate of return"-typed entity (a real FIBO
    subclass of quantity value, confirmed via the 2026-07-14 live-data
    investigation) must no longer dominate degree_centrality's ranking
    purely by co-occurring with every fact that cites a rate."""
    neo4j, graphdb, settings, graph_id = neo4j_and_graphdb
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="hub", label="Hub", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="rate", label="8.45%", type_="rate of return", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id="e1", source_id="hub", target_id="rate", type_="reports", weight=1.0)

    scores = analytics_service.run_default_analysis(
        neo4j, graph_id, graphdb=graphdb, repository=settings.graphdb_repository,
    )

    assert scores["rate"] == 0.0
    assert scores["hub"] > 0.0
