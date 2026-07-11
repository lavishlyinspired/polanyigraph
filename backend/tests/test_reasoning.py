"""Behavior tests for the neurosymbolic reasoning loop (PLAN.md §8.4).

These encode the acceptance criteria: persistent activation, genuine multi-hop
derivation, and honest convergence reporting.
"""

from __future__ import annotations

from reasoning.engine import Edge, Node, Rule, reason, spread_activation


def _chain():
    """A -> B -> C, all connected so activation can reach C only via B."""
    nodes = [
        Node(id="A", label="A", type="T"),
        Node(id="B", label="B", type="T"),
        Node(id="C", label="C", type="T"),
    ]
    edges = [
        Edge(id="e1", source="A", target="B", type="R", weight=1.0),
        Edge(id="e2", source="B", target="C", type="R", weight=1.0),
    ]
    return nodes, edges


def test_spread_is_directed():
    nodes, edges = _chain()
    act = spread_activation(nodes, edges, "A", decay=0.5)
    # Forward reaches B and C; nothing flows backward into A beyond its own 1.0.
    assert act["A"] == 1.0
    assert act["B"] == 0.5
    assert act["C"] == 0.25


def test_spread_fixpoint_is_order_independent():
    nodes, edges = _chain()
    forward = spread_activation(nodes, edges, "A", decay=0.5)
    reversed_edges = list(reversed(edges))
    assert spread_activation(nodes, reversed_edges, "A", decay=0.5) == forward


def test_multi_hop_derivation_via_persistent_feedback():
    """A rule with a threshold C can only meet AFTER B's derivation boosts it.

    This fails on the prototype (activation reset each iteration); it passes only
    because feedback persists into the next spread.
    """
    nodes, edges = _chain()
    rules = [
        # Threshold 0.6: A (1.0) fires A->B in iter 1, but B's spread activation
        # (0.5) is BELOW threshold, so B->C cannot fire until feedback lifts B.
        Rule(id="r1", name="hop", edge_type="R", source_type="T", target_type="T", threshold=0.6),
    ]
    result = reason(nodes, edges, rules, "A", decay=0.5, feedback_gain=1.0, max_iterations=10)

    derived_edges = {(f.source_id, f.target_id) for f in result.facts}
    # A->B derived in iter 1; B boosted past 0.6; B->C then derivable in iter >= 2.
    assert ("A", "B") in derived_edges
    assert ("B", "C") in derived_edges
    assert any(f.target_id == "C" and f.iteration >= 2 for f in result.facts)


def test_reports_fixpoint_when_stable():
    nodes, edges = _chain()
    rules = [Rule(id="r1", name="hop", edge_type="R", source_type="T", target_type="T", threshold=0.4)]
    result = reason(nodes, edges, rules, "A", decay=0.5, feedback_gain=1.0)
    assert result.converged_by == "fixpoint"
    assert result.iterations < 10


def test_reports_max_iterations_when_capped():
    nodes, edges = _chain()
    rules = [Rule(id="r1", name="hop", edge_type="R", source_type="T", target_type="T", threshold=0.4)]
    result = reason(nodes, edges, rules, "A", decay=0.5, feedback_gain=1.0, max_iterations=1)
    # One iteration cannot both derive and prove stability, so it must not claim fixpoint.
    assert result.converged_by == "max_iterations"
    assert result.iterations == 1


def test_confidence_is_bounded():
    nodes, edges = _chain()
    rules = [Rule(id="r1", name="hop", edge_type="R", source_type="T", target_type="T", threshold=0.1, weight=1.0)]
    result = reason(nodes, edges, rules, "A", decay=0.5, feedback_gain=1.0)
    assert all(0.0 <= f.confidence <= 1.0 for f in result.facts)
