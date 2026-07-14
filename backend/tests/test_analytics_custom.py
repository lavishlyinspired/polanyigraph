"""Unit + integration tests for analytics/algorithms/custom.py (PLAN: plans/
analytical-engine.md Slice 7). Uses the real dataclasses from
reasoning/engine.py (Node, Edge, Rule, DerivedFact, ProofStep) -- not
reinvented shapes -- and one integration test runs the real reasoning
engine (reasoning.engine.reason, pure/no DB) to get real DerivedFact output
to analyze, per the plan's own acceptance criterion.
"""

from __future__ import annotations

from analytics.algorithms.custom import activation_patterns, fact_impact, proof_chain_analysis, rule_coverage
from analytics.projection import build_graph
from reasoning.engine import DerivedFact, Edge, Node, ProofStep, Rule, reason
from services.graph_service import GraphNodeRecord


def test_activation_patterns_identifies_high_activation_nodes():
    nodes = [
        GraphNodeRecord(id="hot", label="hot", type="t", activation=0.9),
        GraphNodeRecord(id="cold", label="cold", type="t", activation=0.1),
    ]
    graph = build_graph(nodes, [])

    result = activation_patterns(graph)

    assert "hot" in result.high_activation_nodes
    assert "cold" not in result.high_activation_nodes


def test_activation_patterns_flags_bottlenecks_as_high_activation_with_no_outgoing_edges():
    from services.graph_service import GraphEdgeRecord

    nodes = [
        GraphNodeRecord(id="stuck", label="stuck", type="t", activation=0.9),
        GraphNodeRecord(id="flowing", label="flowing", type="t", activation=0.9),
        GraphNodeRecord(id="downstream", label="downstream", type="t", activation=0.1),
    ]
    edges = [GraphEdgeRecord(id="e1", source="flowing", target="downstream", type="rel")]
    graph = build_graph(nodes, edges)

    result = activation_patterns(graph)

    assert "stuck" in result.bottlenecks
    assert "flowing" not in result.bottlenecks


def test_activation_patterns_treats_missing_activation_as_zero():
    nodes = [GraphNodeRecord(id="no_activation", label="n", type="t")]
    graph = build_graph(nodes, [])

    result = activation_patterns(graph)

    assert "no_activation" not in result.high_activation_nodes


def _rule(rule_id: str) -> Rule:
    return Rule(id=rule_id, name=rule_id, edge_type="rel", source_type="t", target_type="t", threshold=0.1)


def _fact(fact_id: str, rule_id: str, source_id: str, target_id: str, proof_path: tuple = ()) -> DerivedFact:
    return DerivedFact(
        id=fact_id, rule_id=rule_id, rule_name=rule_id, source_id=source_id, target_id=target_id,
        fact=f"{source_id}-{target_id}", confidence=0.8, iteration=1, proof_path=proof_path,
    )


def test_rule_coverage_reports_fired_and_never_fired_rules():
    rules = [_rule("r1"), _rule("r2"), _rule("r3")]
    facts = [_fact("f1", "r1", "a", "b"), _fact("f2", "r1", "b", "c"), _fact("f3", "r2", "x", "y")]

    coverage = rule_coverage(rules, facts)

    assert coverage.fired_rule_ids == {"r1", "r2"}
    assert coverage.never_fired_rule_ids == {"r3"}
    assert coverage.fire_counts == {"r1": 2, "r2": 1}


def test_rule_coverage_flags_under_activated_rules_relative_to_others():
    rules = [_rule("r1"), _rule("r2")]
    facts = [_fact("f1", "r1", "a", "b"), _fact("f2", "r1", "b", "c"), _fact("f3", "r1", "c", "d"), _fact("f4", "r2", "x", "y")]

    coverage = rule_coverage(rules, facts)

    assert "r2" in coverage.under_activated_rule_ids  # fired once, well below r1's 3
    assert "r1" not in coverage.under_activated_rule_ids


def test_rule_coverage_does_not_flag_rules_firing_exactly_at_the_mean():
    """r1 and r2 both fire twice -- mean is 2, both are AT the mean, not
    below it. Neither should be under-activated (catches <= vs < at the
    boundary)."""
    rules = [_rule("r1"), _rule("r2")]
    facts = [_fact("f1", "r1", "a", "b"), _fact("f2", "r1", "b", "c"), _fact("f3", "r2", "x", "y"), _fact("f4", "r2", "y", "z")]

    coverage = rule_coverage(rules, facts)

    assert coverage.under_activated_rule_ids == set()


def test_proof_chain_analysis_reports_max_depth_and_rule_usage():
    step = ProofStep(rule_name="r1", edge_type="rel", source_label="a", target_label="b", premise_activation=0.5, iteration=1)
    facts = [
        _fact("f1", "r1", "a", "b", proof_path=(step,)),
        _fact("f2", "r2", "x", "y", proof_path=()),
    ]

    analysis = proof_chain_analysis(facts)

    assert analysis.max_proof_depth == 1
    assert analysis.rule_usage_frequency == {"r1": 1, "r2": 1}


def test_proof_chain_analysis_detects_circular_derivations():
    """a -> b -> c -> a: fact3's target feeds back into fact1's source."""
    facts = [_fact("f1", "r1", "a", "b"), _fact("f2", "r1", "b", "c"), _fact("f3", "r1", "c", "a")]

    analysis = proof_chain_analysis(facts)

    assert {"f1", "f2", "f3"} <= analysis.circular_fact_ids


def test_proof_chain_analysis_reports_no_circularity_for_a_linear_chain():
    facts = [_fact("f1", "r1", "a", "b"), _fact("f2", "r1", "b", "c")]

    analysis = proof_chain_analysis(facts)

    assert analysis.circular_fact_ids == set()


def test_fact_impact_walks_dependent_facts_forward_depth_grouped():
    """f1 concludes a->b. f2 uses b as a premise (b->c) -- depends on f1,
    depth 1. f3 uses c as a premise (c->d) -- depends on f2, depth 2."""
    facts = [
        _fact("f1", "r1", "a", "b"),
        _fact("f2", "r1", "b", "c"),
        _fact("f3", "r1", "c", "d"),
        _fact("unrelated", "r1", "x", "y"),
    ]

    impacted = fact_impact(facts, "f1")

    by_id = {i.fact_id: i.depth for i in impacted}
    assert by_id["f2"] == 1
    assert by_id["f3"] == 2
    assert "unrelated" not in by_id


def test_fact_impact_of_unknown_fact_id_returns_empty():
    facts = [_fact("f1", "r1", "a", "b")]

    assert fact_impact(facts, "does-not-exist") == []


def test_custom_analytics_against_real_reasoning_engine_output():
    """Integration test: real reasoning.engine.reason() (pure, no DB) on a
    small fixture graph, then run the custom analytics on its actual output."""
    nodes = [
        Node(id="finma", label="FINMA", type="regulator"),
        Node(id="bank", label="Bank", type="organization"),
        Node(id="branch", label="Branch", type="organization"),
    ]
    edges = [
        Edge(id="e1", source="finma", target="bank", type="regulates"),
        Edge(id="e2", source="bank", target="branch", type="controls"),
    ]
    rules = [
        Rule(id="r-oversight", name="oversight", edge_type="regulates", source_type="regulator", target_type="organization", threshold=0.1),
        Rule(id="r-control", name="control", edge_type="controls", source_type="organization", target_type="organization", threshold=0.1),
    ]

    result = reason(nodes, edges, rules, source_id="finma")

    coverage = rule_coverage(rules, list(result.facts))
    analysis = proof_chain_analysis(list(result.facts))

    assert isinstance(coverage.fired_rule_ids, set)
    assert isinstance(analysis.max_proof_depth, int)
