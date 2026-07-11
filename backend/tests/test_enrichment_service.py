"""Integration tests for services/enrichment_service.py against live Neo4j
(PLAN.md §19.5): :ImplicitFact is a third, distinct provenance layer, kept
separate from the ontology-typed :Entity graph and the rule-derived
:DerivedFact graph. Pending facts require human-in-the-loop approval (§7.3)
before being queryable as approved."""

from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from db.neo4j_client import Neo4jClient
from enrichment.heuristics.base import ImplicitFactCandidate
from services import enrichment_service, graph_service


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
    client.run("MATCH (f:ImplicitFact {graphId: $gid}) DETACH DELETE f", gid=graph_id)
    client.close()


def test_save_pending_facts_creates_implicit_fact_anchored_to_entity(neo4j):
    client, graph_id = neo4j
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="e1", label="the match", type_="event", source_doc="d", extraction_confidence=1.0)
    candidate = ImplicitFactCandidate(
        heuristic_type="causal_relation", text="The heavy rain caused the postponement.",
        confidence=0.9, anchor_entity_ids=("e1",),
    )

    ids = enrichment_service.save_pending_facts(client, graph_id=graph_id, source_doc="d1", candidates=[candidate])

    assert len(ids) == 1
    pending = enrichment_service.list_pending_facts(client, graph_id)
    assert len(pending) == 1
    assert pending[0].id == ids[0]
    assert pending[0].heuristic_type == "causal_relation"
    assert pending[0].status == "pending"
    assert pending[0].anchor_entity_ids == ("e1",)


def test_approved_facts_are_not_pending_and_pending_facts_are_not_approved(neo4j):
    client, graph_id = neo4j
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="e1", label="the match", type_="event", source_doc="d", extraction_confidence=1.0)
    candidate = ImplicitFactCandidate(heuristic_type="causal_relation", text="fact", confidence=0.9, anchor_entity_ids=("e1",))
    [fact_id] = enrichment_service.save_pending_facts(client, graph_id=graph_id, source_doc="d1", candidates=[candidate])

    enrichment_service.set_fact_status(client, graph_id=graph_id, fact_id=fact_id, status="approved")

    assert enrichment_service.list_pending_facts(client, graph_id) == []
    approved = enrichment_service.list_approved_facts(client, graph_id)
    assert len(approved) == 1
    assert approved[0].status == "approved"


def test_rejected_facts_disappear_from_both_pending_and_approved(neo4j):
    client, graph_id = neo4j
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="e1", label="the match", type_="event", source_doc="d", extraction_confidence=1.0)
    candidate = ImplicitFactCandidate(heuristic_type="causal_relation", text="fact", confidence=0.9, anchor_entity_ids=("e1",))
    [fact_id] = enrichment_service.save_pending_facts(client, graph_id=graph_id, source_doc="d1", candidates=[candidate])

    enrichment_service.set_fact_status(client, graph_id=graph_id, fact_id=fact_id, status="rejected")

    assert enrichment_service.list_pending_facts(client, graph_id) == []
    assert enrichment_service.list_approved_facts(client, graph_id) == []


def test_set_fact_status_rejects_invalid_status(neo4j):
    client, graph_id = neo4j
    with pytest.raises(ValueError):
        enrichment_service.set_fact_status(client, graph_id=graph_id, fact_id="no-such-fact", status="not-a-real-status")


def test_empty_graph_has_no_pending_facts(neo4j):
    client, graph_id = neo4j
    assert enrichment_service.list_pending_facts(client, graph_id) == []
