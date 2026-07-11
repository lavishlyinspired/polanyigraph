"""Integration tests for custom rule storage (Rules Manager add/delete).

Custom rules are stored in Neo4j (global, not graph-scoped -- rules describe
relationships in the ontology, which is shared across graphs using it), kept
separate from the hand-authored seed file (data/rules/fibo_rules.json), which
stays read-only/non-deletable.
"""

from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from db.neo4j_client import Neo4jClient
from services import rules_store


@pytest.fixture
def neo4j():
    client = Neo4jClient(get_settings())
    try:
        client.verify()
    except Exception:
        pytest.skip("Neo4j not reachable")
    rule_id = f"test-rule-{uuid.uuid4().hex[:8]}"
    yield client, rule_id
    client.run("MATCH (r:Rule {id: $rid}) DETACH DELETE r", rid=rule_id)
    client.close()


def test_create_and_list_custom_rule(neo4j):
    client, rule_id = neo4j
    rules_store.create_rule(
        client, rule_id=rule_id, name="Test Rule", edge_type="issues",
        source_type="organization", target_type="security", threshold=0.4,
        weight=1.0, description="{source} issues {target}",
    )

    rules = rules_store.list_custom_rules(client)

    match = next(r for r in rules if r.id == rule_id)
    assert match.name == "Test Rule"
    assert match.threshold == 0.4


def test_delete_custom_rule(neo4j):
    client, rule_id = neo4j
    rules_store.create_rule(
        client, rule_id=rule_id, name="Test Rule", edge_type="issues",
        source_type="organization", target_type="security", threshold=0.4,
        weight=1.0, description="{source} issues {target}",
    )

    deleted = rules_store.delete_rule(client, rule_id)

    assert deleted is True
    assert rule_id not in {r.id for r in rules_store.list_custom_rules(client)}


def test_delete_nonexistent_rule_returns_false(neo4j):
    client, _ = neo4j
    assert rules_store.delete_rule(client, "no-such-rule-xyz") is False
