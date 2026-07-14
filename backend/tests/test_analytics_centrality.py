"""Unit tests for analytics/algorithms/centrality.py (pure, no DB)."""

from __future__ import annotations

from analytics.projection import build_graph
from analytics.result import AlgorithmResult
from analytics.algorithms.centrality import degree_centrality
from services.graph_service import GraphEdgeRecord, GraphNodeRecord


def _star_graph():
    """Hub node "h" connected to three leaves -- hub has the highest degree."""
    nodes = [GraphNodeRecord(id=n, label=n, type="t") for n in ("h", "a", "b", "c")]
    edges = [
        GraphEdgeRecord(id="e1", source="h", target="a", type="rel"),
        GraphEdgeRecord(id="e2", source="h", target="b", type="rel"),
        GraphEdgeRecord(id="e3", source="h", target="c", type="rel"),
    ]
    return build_graph(nodes, edges)


def test_degree_centrality_ranks_the_hub_highest():
    graph = _star_graph()

    result = degree_centrality(graph)

    assert isinstance(result, AlgorithmResult)
    assert result.algorithm == "degree_centrality"
    assert result.node_scores["h"] > result.node_scores["a"]
    assert result.node_scores["h"] > result.node_scores["b"]
    assert result.node_scores["h"] > result.node_scores["c"]


def test_degree_centrality_is_normalized_between_zero_and_one():
    graph = _star_graph()

    result = degree_centrality(graph)

    assert all(0.0 <= score <= 1.0 for score in result.node_scores.values())


def test_degree_centrality_on_empty_graph_returns_empty_scores():
    import networkx as nx

    result = degree_centrality(nx.DiGraph())

    assert result.node_scores == {}
