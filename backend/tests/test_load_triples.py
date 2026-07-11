"""Integration test: stored + derived triples load correctly from Neo4j."""

from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from db.neo4j_client import Neo4jClient
from reasoning.engine import DerivedFact, ProofStep
from services import graph_service
from services.query_engine import Triple


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
    client.run("MATCH (f:DerivedFact {graphId: $gid}) DETACH DELETE f", gid=graph_id)
    client.close()


def test_load_triples_includes_stored_and_derived(neo4j):
    client, graph_id = neo4j
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="org1", label="Acme Corp", type_="organization", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="sec1", label="Acme Stock", type_="security", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_relationship(client, graph_id=graph_id, edge_id="e1", source_id="org1", target_id="sec1", type_="issues", weight=1.0)

    step = ProofStep(rule_name="r", edge_type="is regulated by", source_label="Acme Corp", target_label="FINMA", premise_activation=1.0, iteration=1)
    fact = DerivedFact(id="f1", rule_id="r1", rule_name="r", source_id="org1", target_id="sec1", fact="x", confidence=0.6, iteration=1, proof_path=(step,))
    graph_service.save_derived_facts(client, graph_id=graph_id, facts=[fact])

    triples = graph_service.load_triples(client, graph_id)

    stored = [t for t in triples if not t.derived]
    derived = [t for t in triples if t.derived]
    assert stored == [Triple(subject="Acme Corp", predicate="issues", object="Acme Stock", derived=False, confidence=1.0)]
    assert len(derived) == 1
    assert derived[0].predicate == "is regulated by"
    assert derived[0].confidence == 0.6
