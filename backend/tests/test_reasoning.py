"""Behavior tests for the neurosymbolic reasoning loop (PLAN.md §8.4).

These encode the acceptance criteria: persistent activation, genuine multi-hop
derivation, and honest convergence reporting.
"""

from __future__ import annotations

from reasoning.engine import DerivedFact, Edge, Node, Rule, feed_back_activation, reason, run_inference, spread_activation


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


# --- Manual step-by-step mode (reason tab prototype parity) -----------------
# The prototype's Reason tab lets a user manually trigger Spread Activation /
# Run Inference / Feed Back as three separate steps, with a full trace of
# which rules fired and which were skipped (and why). This requires the
# engine to expose that trace, not just the fired facts, and a standalone
# feedback step -- both already separable from reason()'s loop.

def test_run_inference_reports_a_trace_of_fired_and_skipped_evaluations():
    nodes, edges = _chain()
    rules = [Rule(id="r1", name="hop", edge_type="R", source_type="T", target_type="T", threshold=0.6)]
    activation = spread_activation(nodes, edges, "A", decay=0.5)  # A=1.0, B=0.5, C=0.25

    new_facts, trace = run_inference(
        nodes, edges, rules, activation, iteration=1,
        existing_fact_ids=frozenset(), facts_by_target={},
    )

    assert len(trace) == 2  # one evaluation per (rule, edge) pair: A->B, B->C
    fired = [t for t in trace if t.fired]
    skipped = [t for t in trace if not t.fired]
    assert len(fired) == 1  # A (1.0) >= 0.6 threshold
    assert len(skipped) == 1  # B (0.5) < 0.6 threshold
    assert fired[0].source_label == "A" and fired[0].target_label == "B"
    assert skipped[0].source_label == "B" and skipped[0].target_label == "C"
    assert skipped[0].source_activation == 0.5
    assert skipped[0].threshold == 0.6
    assert {f.id for f in new_facts} == {t.fact_id for t in fired}


def test_run_inference_trace_reports_skip_reason_for_type_mismatch():
    nodes, edges = _chain()
    rules = [Rule(id="r1", name="hop", edge_type="R", source_type="OtherType", target_type="T", threshold=0.1)]
    activation = spread_activation(nodes, edges, "A", decay=0.5)

    _new_facts, trace = run_inference(
        nodes, edges, rules, activation, iteration=1,
        existing_fact_ids=frozenset(), facts_by_target={},
    )

    assert len(trace) == 2
    assert all(not t.fired for t in trace)
    assert all("type" in t.skip_reason.lower() for t in trace)


def test_feed_back_activation_boosts_target_by_confidence_times_gain():
    fact = DerivedFact(
        id="f1", rule_id="r1", rule_name="hop", source_id="A", target_id="B",
        fact="A -> B", confidence=0.8, iteration=1,
    )
    activation = {"A": 1.0, "B": 0.2}

    boosted = feed_back_activation(activation, [fact], feedback_gain=0.5)

    assert boosted["B"] == 0.2 + 0.8 * 0.5
    assert boosted["A"] == 1.0  # untouched, not a target of any fact
    assert activation["B"] == 0.2  # pure function -- input untouched


def test_feed_back_activation_caps_at_one():
    fact = DerivedFact(
        id="f1", rule_id="r1", rule_name="hop", source_id="A", target_id="B",
        fact="A -> B", confidence=1.0, iteration=1,
    )
    boosted = feed_back_activation({"B": 0.9}, [fact], feedback_gain=1.0)
    assert boosted["B"] == 1.0


def test_reason_still_produces_identical_results_with_the_refactored_feedback():
    """Regression guard: reason() now calls feed_back_activation() internally
    instead of an inline loop -- behavior must be byte-for-byte identical."""
    nodes, edges = _chain()
    rules = [Rule(id="r1", name="hop", edge_type="R", source_type="T", target_type="T", threshold=0.6)]
    result = reason(nodes, edges, rules, "A", decay=0.5, feedback_gain=1.0, max_iterations=10)

    derived_edges = {(f.source_id, f.target_id) for f in result.facts}
    assert ("A", "B") in derived_edges
    assert ("B", "C") in derived_edges
    assert result.converged_by == "fixpoint"
