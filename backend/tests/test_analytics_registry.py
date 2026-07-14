"""Unit tests for analytics/registry.py's AlgorithmRegistry (pure, no DB)."""

from __future__ import annotations

from analytics.registry import AlgorithmRegistry, AlgorithmSpec, default_registry


def test_register_and_get_returns_the_spec():
    registry = AlgorithmRegistry()
    spec = AlgorithmSpec(name="my_algo", category="centrality", func=lambda g: {})

    registry.register(spec)

    assert registry.get("my_algo") is spec


def test_get_unknown_algorithm_returns_none():
    registry = AlgorithmRegistry()

    assert registry.get("does_not_exist") is None


def test_list_returns_all_registered_specs():
    registry = AlgorithmRegistry()
    spec_a = AlgorithmSpec(name="a", category="centrality", func=lambda g: {})
    spec_b = AlgorithmSpec(name="b", category="community", func=lambda g: {})
    registry.register(spec_a)
    registry.register(spec_b)

    names = {spec.name for spec in registry.list()}

    assert names == {"a", "b"}


def test_default_registry_has_all_four_centrality_algorithms():
    names = {spec.name for spec in default_registry.list()}

    assert {"degree_centrality", "pagerank", "betweenness_centrality", "closeness_centrality"} <= names
    for spec in default_registry.list():
        if spec.name in {"degree_centrality", "pagerank", "betweenness_centrality", "closeness_centrality"}:
            assert spec.category == "centrality"


def test_default_registry_centrality_algorithms_suggest_a_bar_chart():
    """Registry-driven chart hint (PLAN Slice 9), not an LLM guess -- ranked
    centrality scores render as a bar chart."""
    for name in ("degree_centrality", "pagerank", "betweenness_centrality", "closeness_centrality"):
        spec = default_registry.get(name)
        assert spec.chart_type == "bar"
