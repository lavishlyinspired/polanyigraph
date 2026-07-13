"""Integration tests for services/reasoning_service.py -- extracted from
api/reason.py so both the REST endpoint and the LangGraph agent's reasoner
node (backend/agents/graph.py) call the same tested reasoning invocation
logic, not two copies of it."""

from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient
from services import graph_service, reasoning_service


@pytest.fixture
def services():
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
    neo4j.run("MATCH (f:DerivedFact {graphId: $gid}) DETACH DELETE f", gid=graph_id)
    neo4j.close()
    graphdb.close()


def test_run_reasoning_derives_and_persists_fact(services):
    neo4j, graphdb, settings, graph_id = services
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="org1", label="Acme Corp", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="sec1", label="Acme Preferred Stock", type_="security", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id="e1", source_id="org1", target_id="sec1", type_="issues", weight=1.0)

    result = reasoning_service.run_reasoning(neo4j, graphdb, settings, graph_id=graph_id, source_id="org1")

    assert result is not None
    fact_texts = {f.fact for f in result.facts}
    assert "Acme Corp issues Acme Preferred Stock" in fact_texts
    # Persisted for real, not just returned -- a second read shows it.
    persisted = graph_service.get_derived_facts(neo4j, graph_id)
    assert any(f["fact"] == "Acme Corp issues Acme Preferred Stock" for f in persisted)


def test_run_reasoning_raises_for_empty_graph(services):
    neo4j, graphdb, settings, graph_id = services
    with pytest.raises(reasoning_service.EmptyGraphError):
        reasoning_service.run_reasoning(neo4j, graphdb, settings, graph_id=graph_id, source_id=None)


def test_run_reasoning_raises_for_unknown_source_id(services):
    neo4j, graphdb, settings, graph_id = services
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="org1", label="Acme Corp", type_="organization", source_doc="d", extraction_confidence=1.0)

    with pytest.raises(reasoning_service.UnknownSourceError):
        reasoning_service.run_reasoning(neo4j, graphdb, settings, graph_id=graph_id, source_id="no-such-node")


def test_run_reasoning_defaults_source_to_first_node(services):
    neo4j, graphdb, settings, graph_id = services
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="org1", label="Acme Corp", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="sec1", label="Acme Preferred Stock", type_="security", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id="e1", source_id="org1", target_id="sec1", type_="issues", weight=1.0)

    result = reasoning_service.run_reasoning(neo4j, graphdb, settings, graph_id=graph_id, source_id=None)

    assert result is not None


def test_review_derived_fact_updates_rule_weight_and_affects_a_later_real_reasoning_run(services):
    """2026-07-13 plan §11.1, end-to-end: reviewing a derived fact updates
    its producing rule's weight (rules_store.update_rule_weight), and a
    LATER run_reasoning call picks up that new weight with zero changes to
    reasoning/engine.py -- the plan's own stated claim, proven against a
    real second reasoning run, not just asserted."""
    neo4j, graphdb, settings, graph_id = services
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="org1", label="Acme Corp", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="sec1", label="Acme Preferred Stock", type_="security", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id="e1", source_id="org1", target_id="sec1", type_="issues", weight=1.0)

    try:
        first_result = reasoning_service.run_reasoning(neo4j, graphdb, settings, graph_id=graph_id, source_id="org1")
        fact = next(f for f in first_result.facts if f.fact == "Acme Corp issues Acme Preferred Stock")
        assert fact.confidence == pytest.approx(1.0)  # activation(1.0) * seed weight(1.0)

        new_weight = reasoning_service.review_derived_fact(neo4j, graph_id=graph_id, fact_id=fact.id, outcome="rejected")
        assert new_weight == pytest.approx(0.0)

        graph_service.clear_derived_facts(neo4j, graph_id)
        graph_service.clear_activation(neo4j, graph_id=graph_id)
        second_result = reasoning_service.run_reasoning(neo4j, graphdb, settings, graph_id=graph_id, source_id="org1")

        second_fact = next(f for f in second_result.facts if f.fact == "Acme Corp issues Acme Preferred Stock")
        assert second_fact.confidence == pytest.approx(0.0)  # activation(1.0) * reviewed weight(0.0)
    finally:
        neo4j.run("MATCH (r:Rule {id: 'issues-security'}) DETACH DELETE r")
        neo4j.run("MATCH (o:RuleReviewOutcome {ruleId: 'issues-security'}) DETACH DELETE o")
