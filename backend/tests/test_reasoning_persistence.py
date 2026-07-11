"""Integration tests: persisting reasoning results back into Neo4j."""

from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from db.neo4j_client import Neo4jClient
from reasoning.engine import DerivedFact, ProofStep
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
    client.run("MATCH (f:DerivedFact {graphId: $gid}) DETACH DELETE f", gid=graph_id)
    client.close()


def _seed(client: Neo4jClient, graph_id: str) -> None:
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="e1", label="A", type_="T", source_doc="d", extraction_confidence=1.0)
    graph_service.upsert_entity(client, graph_id=graph_id, entity_id="e2", label="B", type_="T", source_doc="d", extraction_confidence=1.0)


def test_apply_activation_updates_entities(neo4j):
    client, graph_id = neo4j
    _seed(client, graph_id)

    graph_service.apply_activation(client, graph_id=graph_id, activation={"e1": 1.0, "e2": 0.45})

    result = graph_service.get_graph(client, graph_id)
    by_id = {n.id: n for n in result.nodes}
    assert by_id["e1"].activation == 1.0
    assert by_id["e2"].activation == 0.45


def test_save_derived_facts_marks_target_derived(neo4j):
    client, graph_id = neo4j
    _seed(client, graph_id)

    step = ProofStep(rule_name="r", edge_type="R", source_label="A", target_label="B", premise_activation=1.0, iteration=1)
    fact = DerivedFact(
        id="fact-1", rule_id="r1", rule_name="r", source_id="e1", target_id="e2",
        fact="A relates B", confidence=0.7, iteration=1, proof_path=(step,),
    )

    graph_service.save_derived_facts(client, graph_id=graph_id, facts=[fact])

    result = graph_service.get_graph(client, graph_id)
    b = next(n for n in result.nodes if n.id == "e2")
    assert b.derived is True

    rows = client.run("MATCH (f:DerivedFact {graphId: $gid}) RETURN f.id AS id, f.confidence AS confidence", gid=graph_id)
    assert rows[0]["id"] == "fact-1"
    assert rows[0]["confidence"] == 0.7
