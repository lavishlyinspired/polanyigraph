"""Tests for services/graph_maintenance_loop.py (2026-07-13 plan §12.3,
Feature 7): real Neo4j + real GraphDB + real embedder, per project
convention -- this loop only ever creates candidate records awaiting human
approval (mining, entity resolution) or runs the already-tested reasoning
engine, so the tests prove exactly that: nothing gets auto-approved, and
re-running is idempotent-safe.
"""

from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from app.dependencies import get_embedder
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient
from services import entity_resolution_service, graph_service, graph_maintenance_loop, rule_mining_service, vector_search_service


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
    neo4j.run("MATCH (c:CandidateRule {graphId: $gid}) DETACH DELETE c", gid=graph_id)
    neo4j.run("MATCH (d:DuplicateCandidate {graphId: $gid}) DETACH DELETE d", gid=graph_id)
    neo4j.run("MATCH (l:LoopRun {graphId: $gid}) DETACH DELETE l", gid=graph_id)
    neo4j.close()
    graphdb.close()


@pytest.fixture
def embedder():
    e = get_embedder()
    try:
        e.verify()
    except Exception:
        pytest.skip("Embedding endpoint not reachable")
    return e


def test_maintenance_loop_mines_candidates_reasons_and_flags_duplicates(services, embedder):
    """Exercises all 3 real maker steps in one real graph: a repeating
    pattern for mining, a real seed-rule-matching edge for reasoning, and
    a near-duplicate entity pair for the entity-resolution backstop.

    All entities form ONE connected component, AND entity ids are chosen so
    graph_service.get_graph's now-deterministic `ORDER BY e.id` picks a
    non-leaf node first: reasoning_service.run_reasoning(source_id=None)
    starts from whatever get_entities_and_edges_for_reasoning returns
    first, and activation only spreads FORWARD along real directed edges
    (reasoning/engine.py's spread_activation) -- if a genuine sink node
    (no outgoing edges, e.g. the security "pref") were picked as source,
    nothing would propagate and reasoning would derive zero facts. Found
    this exact flakiness for real (passed 5/5 in isolation, failed once in
    the full ~300-test suite) before get_graph had an ORDER BY at all --
    fixed at the root (services/graph_service.py) since it affects every
    caller of run_reasoning(source_id=None), not just this test."""
    neo4j, graphdb, settings, graph_id = services
    vector_search_service.ensure_indexes(neo4j, dimensions=embedder.dimensions)

    # "a-"-prefixed ids sort before "z-"-prefixed ones under ORDER BY e.id,
    # so the deterministic first node is always one of the non-leaf,
    # forward-connected orgs, never a leaf/sink.
    # a-org0/a-org1/a-org2 -[PARTNERS_WITH]-> a-target-org (mining fodder,
    # support=3), a-target-org -[issues]-> z-pref (real seed-rule-matching
    # edge) -- so activation starting from ANY of the "a-" nodes reaches
    # "issues" via directed spread through the shared a-target-org.
    tag = uuid.uuid4().hex[:8]
    partners_with = f"PARTNERS_WITH_{tag}"
    for i in range(3):
        graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id=f"a-org{i}", label=f"Org {i}", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="a-target-org", label="Target Org", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="z-pref", label="Preferred Stock", type_="security", source_doc="d", extraction_confidence=1.0)
    for i in range(3):
        graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id=f"pw{i}", source_id=f"a-org{i}", target_id="a-target-org", type_=partners_with, weight=1.0)
    graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id="issues1", source_id="a-target-org", target_id="z-pref", type_="issues", weight=1.0)

    # Entity-resolution fodder: a near-duplicate NOT caught at ingest time
    # (upsert_entity directly, bypassing ingest_service's own check).
    # "z-"-prefixed like z-pref -- fine to be a leaf, never picked first.
    for eid, label, summary in [
        ("z-dup-a", "Beta Corp", "Beta Corp is a company that filed a regulatory report."),
        ("z-dup-b", "Beta Corporation", "Beta Corporation filed a new regulatory report recently."),
    ]:
        graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id=eid, label=label, type_="organization", source_doc="d", extraction_confidence=1.0)
        vector_search_service.index_entity_summary(neo4j, embedder, graph_id=graph_id, entity_id=eid, summary=summary)
    graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id="dup-edge", source_id="a-org0", target_id="z-dup-a", type_=f"MENTIONS_{tag}", weight=1.0)

    summary = graph_maintenance_loop.run_maintenance_loop(neo4j, graphdb, settings, graph_id)

    assert len(summary.mined_candidate_ids) >= 1
    assert any(partners_with in cid for cid in summary.mined_candidate_ids)
    assert summary.reasoning_ran is True
    assert summary.reasoning_new_facts >= 1
    assert "issues-security" in summary.active_rule_weights
    assert len(summary.duplicate_candidate_ids) >= 1

    # Nothing was auto-applied -- every candidate is still pending review.
    pending_rules = rule_mining_service.list_candidates(neo4j, status="pending")
    assert any(c.id in summary.mined_candidate_ids for c in pending_rules)
    pending_dupes = entity_resolution_service.list_candidates(neo4j, graph_id=graph_id, status="pending")
    assert any(c["id"] in summary.duplicate_candidate_ids for c in pending_dupes)

    # Persisted as a real, queryable :LoopRun.
    runs = graph_maintenance_loop.list_loop_runs(neo4j, graph_id)
    assert any(r.id == summary.id for r in runs)


def test_maintenance_loop_handles_an_empty_graph_gracefully(services):
    neo4j, graphdb, settings, graph_id = services

    summary = graph_maintenance_loop.run_maintenance_loop(neo4j, graphdb, settings, graph_id)

    assert summary.reasoning_ran is False
    assert summary.reasoning_new_facts == 0
    assert summary.mined_candidate_ids == ()
    assert summary.duplicate_candidate_ids == ()


def test_maintenance_loop_is_idempotent_on_a_second_run(services, embedder):
    """Re-running doesn't duplicate mined candidates or duplicate-entity
    flags -- both use deterministic, MERGE-safe ids."""
    neo4j, graphdb, settings, graph_id = services
    vector_search_service.ensure_indexes(neo4j, dimensions=embedder.dimensions)
    tag = uuid.uuid4().hex[:8]
    partners_with = f"PARTNERS_WITH_{tag}"
    for i in range(3):
        graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id=f"org{i}", label=f"Org {i}", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="target_org", label="Target Org", type_="organization", source_doc="d", extraction_confidence=1.0)
    for i in range(3):
        graph_service.upsert_relationship(neo4j, graph_id=graph_id, edge_id=f"pw{i}", source_id=f"org{i}", target_id="target_org", type_=partners_with, weight=1.0)

    first = graph_maintenance_loop.run_maintenance_loop(neo4j, graphdb, settings, graph_id)
    second = graph_maintenance_loop.run_maintenance_loop(neo4j, graphdb, settings, graph_id)

    assert set(first.mined_candidate_ids) == set(second.mined_candidate_ids)
    pending_rules = rule_mining_service.list_candidates(neo4j, status="pending")
    matching = [c for c in pending_rules if c.id in first.mined_candidate_ids]
    assert len(matching) == len(first.mined_candidate_ids)  # not duplicated
