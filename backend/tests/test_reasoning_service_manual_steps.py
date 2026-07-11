"""Integration tests for services/reasoning_service.py's manual step-by-step
mode (Reason tab prototype parity, PLAN.md §16 Phase 9): the prototype lets a
user trigger Spread Activation / Run Inference / Feed Back as three separate
steps rather than only the atomic run_reasoning() that runs to convergence.
Each step must read/write REAL persisted Neo4j state so it survives across
separate calls, not just an in-memory single-request computation."""

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


def _chain(neo4j, graph_id):
    """A -> B -> C, matching test_reasoning.py's engine-level fixture. Types
    are synthetic ("T") and the edge type is unique to this test file, on
    purpose -- upsert_entity/upsert_relationship don't validate against the
    ontology (that happens at the API layer), and using a synthetic type
    guarantees no real seed rule (which reference real FIBO types) can
    accidentally also fire and break the "exactly 1 new fact" assertion."""
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="A", label="A", type_="T", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="B", label="B", type_="T", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="C", label="C", type_="T", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id="e1", source_id="A", target_id="B", type_="test-hop-edge", weight=1.0)
    graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id="e2", source_id="B", target_id="C", type_="test-hop-edge", weight=1.0)


def test_spread_activation_step_persists_real_activation(services):
    neo4j, graphdb, settings, graph_id = services
    _chain(neo4j, graph_id)

    activation = reasoning_service.spread_activation_step(neo4j, graph_id, "A", decay=0.5)

    assert activation["A"] == 1.0
    assert activation["B"] == 0.5
    # Persisted for real -- a fresh read confirms it, not just the return value.
    record = graph_service.get_graph(neo4j, graph_id)
    b = next(n for n in record.nodes if n.id == "B")
    assert b.activation == 0.5


def test_spread_activation_step_accumulates_on_repeated_calls(services):
    """Persistent activation (PLAN.md §8.4): a second spread seeded with the
    first's persisted result should not reset to zero first."""
    neo4j, graphdb, settings, graph_id = services
    _chain(neo4j, graph_id)

    reasoning_service.spread_activation_step(neo4j, graph_id, "A", decay=0.5)
    # Manually boost B beyond what a fresh spread from A alone would give it.
    graph_service.apply_activation(neo4j, graph_id=graph_id, activation={"B": 0.9})

    activation = reasoning_service.spread_activation_step(neo4j, graph_id, "A", decay=0.5)

    assert activation["B"] == 0.9  # max-activation fixpoint: seed already higher than fresh spread


def test_run_inference_step_persists_facts_and_returns_trace(services):
    neo4j, graphdb, settings, graph_id = services
    from services.rules_store import create_rule
    rule_id = f"{graph_id}:test-rule"
    try:
        _chain(neo4j, graph_id)
        create_rule(
            neo4j, rule_id=rule_id, name="test-hop-rule", edge_type="test-hop-edge",
            source_type="T", target_type="T", threshold=0.6, weight=1.0, description="{source} -> {target}",
        )
        reasoning_service.spread_activation_step(neo4j, graph_id, "A", decay=0.5)

        new_facts, trace = reasoning_service.run_inference_step(neo4j, graphdb, settings, graph_id)

        assert len(new_facts) == 1
        assert new_facts[0].source_id == "A" and new_facts[0].target_id == "B"
        assert len(trace) >= 1
        assert any(t.fired for t in trace)

        # Persisted for real.
        full = graph_service.get_derived_facts_full(neo4j, graph_id)
        assert len(full) == 1
        assert full[0].fed_back is False
    finally:
        neo4j.run("MATCH (r:Rule {id: $rid}) DETACH DELETE r", rid=rule_id)


def test_feed_back_step_boosts_activation_and_marks_facts(services):
    neo4j, graphdb, settings, graph_id = services
    _chain(neo4j, graph_id)
    from reasoning.engine import DerivedFact as ReasoningDerivedFact
    fact = ReasoningDerivedFact(id=f"{graph_id}:f1", rule_id="r1", rule_name="hop", source_id="A", target_id="B", fact="A issues B", confidence=0.8, iteration=1)
    graph_service.save_derived_facts(neo4j, graph_id=graph_id, facts=[fact])
    graph_service.apply_activation(neo4j, graph_id=graph_id, activation={"B": 0.1})

    activation = reasoning_service.feed_back_step(neo4j, graph_id, feedback_gain=0.5)

    assert activation["B"] == pytest.approx(0.1 + 0.8 * 0.5)
    full = graph_service.get_derived_facts_full(neo4j, graph_id)
    assert full[0].fed_back is True


def test_feed_back_step_only_boosts_from_pending_not_already_fed_back(services):
    neo4j, graphdb, settings, graph_id = services
    _chain(neo4j, graph_id)
    from reasoning.engine import DerivedFact as ReasoningDerivedFact
    fact = ReasoningDerivedFact(id=f"{graph_id}:f1", rule_id="r1", rule_name="hop", source_id="A", target_id="B", fact="A issues B", confidence=0.8, iteration=1)
    graph_service.save_derived_facts(neo4j, graph_id=graph_id, facts=[fact])

    reasoning_service.feed_back_step(neo4j, graph_id, feedback_gain=0.5)  # first feed back: consumes it
    activation_before_second = graph_service.get_graph(neo4j, graph_id)
    b_before = next(n for n in activation_before_second.nodes if n.id == "B").activation

    reasoning_service.feed_back_step(neo4j, graph_id, feedback_gain=0.5)  # nothing pending now

    activation_after = graph_service.get_graph(neo4j, graph_id)
    b_after = next(n for n in activation_after.nodes if n.id == "B").activation
    assert b_after == b_before  # unchanged -- no double-counting the same fact
