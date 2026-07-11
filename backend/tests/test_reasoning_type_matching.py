"""Reasoning engine accepts an injectable type-matching function, defaulting to
exact equality (existing tests / behavior untouched) but pluggable with an
ontology-aware matcher (see ontology/schema.py build_subclass_matcher). This
keeps reasoning/engine.py dependency-free from GraphDB/ontology while still
fixing the real gap: extracted subclasses ("commercial bank") not matching
rules written against generic ancestor types ("organization").
"""

from __future__ import annotations

from reasoning.engine import Edge, Node, Rule, reason


def test_default_matching_is_exact_and_unchanged():
    nodes = [Node(id="a", label="A", type="commercial bank"), Node(id="b", label="B", type="security")]
    edges = [Edge(id="e1", source="a", target="b", type="issues")]
    rules = [Rule(id="r1", name="issues", edge_type="issues", source_type="organization", target_type="security", threshold=0.1)]

    result = reason(nodes, edges, rules, "a", decay=0.5)
    assert result.facts == ()  # "commercial bank" != "organization" under exact match


def test_injected_ontology_aware_matcher_fixes_the_real_gap():
    nodes = [Node(id="a", label="A", type="commercial bank"), Node(id="b", label="B", type="security")]
    edges = [Edge(id="e1", source="a", target="b", type="issues")]
    rules = [Rule(id="r1", name="issues", edge_type="issues", source_type="organization", target_type="security", threshold=0.1)]

    def is_a(candidate: str, expected: str) -> bool:
        return candidate == expected or (candidate == "commercial bank" and expected == "organization")

    result = reason(nodes, edges, rules, "a", decay=0.5, type_matches=is_a)
    assert len(result.facts) == 1
    assert result.facts[0].fact == "A -> B"


def test_proof_step_explains_ontology_resolution_when_types_differ():
    """UI requirement: ontology resolution must be visible, not silent."""
    nodes = [Node(id="a", label="A", type="commercial bank"), Node(id="b", label="B", type="security")]
    edges = [Edge(id="e1", source="a", target="b", type="issues")]
    rules = [Rule(id="r1", name="issues", edge_type="issues", source_type="organization", target_type="security", threshold=0.1)]

    def is_a(candidate: str, expected: str) -> bool:
        return candidate == expected or (candidate == "commercial bank" and expected == "organization")

    result = reason(nodes, edges, rules, "a", decay=0.5, type_matches=is_a)
    step = result.facts[0].proof_path[-1]
    assert step.type_resolution is not None
    assert "commercial bank" in step.type_resolution
    assert "organization" in step.type_resolution


def test_proof_step_has_no_resolution_note_on_exact_match():
    nodes = [Node(id="a", label="A", type="organization"), Node(id="b", label="B", type="security")]
    edges = [Edge(id="e1", source="a", target="b", type="issues")]
    rules = [Rule(id="r1", name="issues", edge_type="issues", source_type="organization", target_type="security", threshold=0.1)]

    result = reason(nodes, edges, rules, "a", decay=0.5)
    step = result.facts[0].proof_path[-1]
    assert step.type_resolution is None
