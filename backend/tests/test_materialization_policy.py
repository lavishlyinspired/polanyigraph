"""Pure-logic tests for materialization/policy.py -- the Semantic
Materialization Engine's decision layer (PLAN Phase 3, .claude/docs/
research/2026-07-14-semantic-materialization-engine-design.md).

v1 scope: only NODE and PROPERTY are ever decided. A concept is inlined as
a PROPERTY only when its ontology role resolves to Value/Temporal/Metadata
(reusing Phase 1's analytics.roles taxonomy unchanged) AND it participates
in exactly one relationship (fanout == 1) -- the real noise pattern found
via live testing: a percentage or a date that's the target of exactly one
fact and nothing else (e.g. `reports(Company, "8.45%")`).
"""

from __future__ import annotations

from analytics.roles import AnalyticsRole
from extraction.pipeline import ExtractedEntity, ExtractedRelationship
from materialization.policy import (
    MaterializationPolicy,
    compute_fanout,
    find_introducing_relationship,
    plan_materialization,
)


def test_value_role_leaf_entity_is_inlined_as_a_property():
    entity = ExtractedEntity(name="8.45%", type="rate of return", confidence=0.9)
    rel = ExtractedRelationship(source="HDFC Bank", relation="reports", target="8.45%", confidence=0.9)

    decision = plan_materialization(entity, AnalyticsRole.VALUE, fanout=1, introducing_relationship=rel)

    assert decision.policy == MaterializationPolicy.PROPERTY
    assert decision.attach_to_entity_name == "HDFC Bank"
    assert decision.property_key == "reports"


def test_temporal_role_leaf_entity_is_inlined_as_a_property():
    entity = ExtractedEntity(name="2026-08-05", type="date", confidence=0.9)
    rel = ExtractedRelationship(source="Filing", relation="filedOn", target="2026-08-05", confidence=0.9)

    decision = plan_materialization(entity, AnalyticsRole.TEMPORAL, fanout=1, introducing_relationship=rel)

    assert decision.policy == MaterializationPolicy.PROPERTY
    assert decision.attach_to_entity_name == "Filing"
    assert decision.property_key == "filedOn"


def test_inlining_works_when_entity_is_the_relationship_source_not_target():
    entity = ExtractedEntity(name="8.45%", type="rate of return", confidence=0.9)
    rel = ExtractedRelationship(source="8.45%", relation="appliesTo", target="HDFC Bank", confidence=0.9)

    decision = plan_materialization(entity, AnalyticsRole.VALUE, fanout=1, introducing_relationship=rel)

    assert decision.policy == MaterializationPolicy.PROPERTY
    assert decision.attach_to_entity_name == "HDFC Bank"


def test_actor_role_entity_stays_a_node_even_with_fanout_one():
    entity = ExtractedEntity(name="HDFC Bank", type="organization", confidence=0.9)
    rel = ExtractedRelationship(source="HDFC Bank", relation="reports", target="8.45%", confidence=0.9)

    decision = plan_materialization(entity, AnalyticsRole.ACTOR, fanout=1, introducing_relationship=rel)

    assert decision.policy == MaterializationPolicy.NODE
    assert decision.attach_to_entity_name is None
    assert decision.property_key is None


def test_value_role_entity_with_fanout_greater_than_one_stays_a_node():
    """Referenced by more than one relationship -- inlining would silently
    drop information about every relationship but one, so it stays a node."""
    entity = ExtractedEntity(name="8.45%", type="rate of return", confidence=0.9)

    decision = plan_materialization(entity, AnalyticsRole.VALUE, fanout=2, introducing_relationship=None)

    assert decision.policy == MaterializationPolicy.NODE


def test_value_role_entity_with_fanout_zero_stays_a_node():
    """Never mentioned in any relationship -- nothing to attach the
    property to, so it stays a node (mirrors today's behavior for an
    isolated extracted entity)."""
    entity = ExtractedEntity(name="8.45%", type="rate of return", confidence=0.9)

    decision = plan_materialization(entity, AnalyticsRole.VALUE, fanout=0, introducing_relationship=None)

    assert decision.policy == MaterializationPolicy.NODE


def test_unresolved_role_stays_a_node():
    entity = ExtractedEntity(name="Something Unmapped", type="unmapped-type", confidence=0.9)
    rel = ExtractedRelationship(source="HDFC Bank", relation="reports", target="Something Unmapped", confidence=0.9)

    decision = plan_materialization(entity, None, fanout=1, introducing_relationship=rel)

    assert decision.policy == MaterializationPolicy.NODE


def test_self_loop_relationship_stays_a_node():
    """Degenerate case: a relationship where source == target == this
    entity's own name -- inlining would attach a property to itself via a
    relationship that no longer makes sense once the node is gone."""
    entity = ExtractedEntity(name="8.45%", type="rate of return", confidence=0.9)
    rel = ExtractedRelationship(source="8.45%", relation="equals", target="8.45%", confidence=0.9)

    decision = plan_materialization(entity, AnalyticsRole.VALUE, fanout=1, introducing_relationship=rel)

    assert decision.policy == MaterializationPolicy.NODE


def test_decision_reason_is_human_auditable():
    entity = ExtractedEntity(name="8.45%", type="rate of return", confidence=0.9)
    rel = ExtractedRelationship(source="HDFC Bank", relation="reports", target="8.45%", confidence=0.9)

    decision = plan_materialization(entity, AnalyticsRole.VALUE, fanout=1, introducing_relationship=rel)

    assert "value" in decision.reason
    assert "reports" in decision.reason


# --- compute_fanout ----------------------------------------------------

def test_compute_fanout_counts_source_and_target_appearances():
    relationships = [
        ExtractedRelationship(source="HDFC Bank", relation="reports", target="8.45%"),
        ExtractedRelationship(source="HDFC Bank", relation="regulatedBy", target="RBI"),
    ]

    fanout = compute_fanout(relationships)

    assert fanout["HDFC Bank"] == 2
    assert fanout["8.45%"] == 1
    assert fanout["RBI"] == 1


def test_compute_fanout_returns_zero_for_an_entity_not_in_any_relationship():
    fanout = compute_fanout([])

    assert fanout.get("anything", 0) == 0


# --- find_introducing_relationship --------------------------------------

def test_find_introducing_relationship_returns_the_single_match():
    relationships = [
        ExtractedRelationship(source="HDFC Bank", relation="reports", target="8.45%"),
        ExtractedRelationship(source="HDFC Bank", relation="regulatedBy", target="RBI"),
    ]

    rel = find_introducing_relationship("8.45%", relationships)

    assert rel is not None
    assert rel.relation == "reports"


def test_find_introducing_relationship_returns_none_when_no_match():
    rel = find_introducing_relationship("nowhere", [])

    assert rel is None
