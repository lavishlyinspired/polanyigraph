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
    client.run("MATCH (o:RuleReviewOutcome {ruleId: $rid}) DETACH DELETE o", rid=rule_id)
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


def test_update_rule_weight_converges_to_a_known_confirm_reject_ratio(neo4j):
    """2026-07-13 plan §11.1's own test spec: a scripted sequence of
    confirm/reject outcomes with a known ratio -- weight converges toward
    that ratio, deterministic given a fixed sequence."""
    client, rule_id = neo4j
    rules_store.create_rule(
        client, rule_id=rule_id, name="Test Rule", edge_type="issues",
        source_type="organization", target_type="security", threshold=0.4,
        weight=1.0, description="{source} issues {target}",
    )

    # 3 confirmed, 1 rejected -> known ratio 3/4 = 0.75
    outcomes = ["confirmed", "confirmed", "rejected", "confirmed"]
    weight = None
    for outcome in outcomes:
        weight = rules_store.update_rule_weight(client, rule_id, outcome=outcome)

    assert weight == pytest.approx(0.75)
    updated = next(r for r in rules_store.list_custom_rules(client) if r.id == rule_id)
    assert updated.weight == pytest.approx(0.75)
    # Reviewing a rule's weight must never silently change what it fires on.
    assert updated.edge_type == "issues"
    assert updated.threshold == 0.4


def test_update_rule_weight_overrides_a_seed_rule_without_duplicating_it(neo4j):
    """A seed rule (read-only JSON, data/rules/fibo_rules.json) can still
    have its weight evolve from review -- stored as a Neo4j :Rule override
    with the seed rule's own id, not a second, duplicate rule."""
    client, _unused_rule_id = neo4j
    seed_id = "issues-security"  # real seed rule id, data/rules/fibo_rules.json

    try:
        new_weight = rules_store.update_rule_weight(client, seed_id, outcome="rejected")

        assert new_weight == pytest.approx(0.0)
        all_rules = rules_store.load_all_rules(client)
        matches = [r for r in all_rules if r.id == seed_id]
        assert len(matches) == 1  # override, not a duplicate
        assert matches[0].weight == pytest.approx(0.0)
        assert matches[0].edge_type == "issues"  # unchanged from the seed definition
    finally:
        client.run("MATCH (r:Rule {id: $rid}) DETACH DELETE r", rid=seed_id)
        client.run("MATCH (o:RuleReviewOutcome {ruleId: $rid}) DETACH DELETE o", rid=seed_id)


def test_update_rule_weight_rejects_an_invalid_outcome(neo4j):
    client, rule_id = neo4j
    rules_store.create_rule(
        client, rule_id=rule_id, name="Test Rule", edge_type="issues",
        source_type="organization", target_type="security", threshold=0.4,
        weight=1.0, description="{source} issues {target}",
    )
    with pytest.raises(ValueError):
        rules_store.update_rule_weight(client, rule_id, outcome="maybe")


def test_update_rule_weight_rejects_an_unknown_rule(neo4j):
    client, _ = neo4j
    with pytest.raises(ValueError):
        rules_store.update_rule_weight(client, "no-such-rule-xyz", outcome="confirmed")
