"""Unit tests for analytics/algorithms/centrality.py (pure, no DB)."""

from __future__ import annotations

from analytics.projection import build_graph
from analytics.algorithms.centrality import betweenness_centrality, closeness_centrality, degree_centrality, pagerank
from services.graph_service import GraphEdgeRecord, GraphNodeRecord


def _star_graph():
    """Hub node "h" connected to three leaves -- hub has the highest degree
    (degree_centrality sums in+out degree, direction-insensitive)."""
    nodes = [GraphNodeRecord(id=n, label=n, type="t") for n in ("h", "a", "b", "c")]
    edges = [
        GraphEdgeRecord(id="e1", source="h", target="a", type="rel"),
        GraphEdgeRecord(id="e2", source="h", target="b", type="rel"),
        GraphEdgeRecord(id="e3", source="h", target="c", type="rel"),
    ]
    return build_graph(nodes, edges)


def _inward_star_graph():
    """Three leaves all pointing INTO hub "h" -- unlike degree_centrality,
    pagerank and closeness_centrality are direction-sensitive: pagerank
    rewards being pointed to (not pointing out), and networkx's directed
    closeness_centrality measures incoming reachability. A hub that only
    emits edges (as in _star_graph) scores *lowest*, not highest, on both --
    this fixture reverses the edges so "hub is central" is actually true
    for these two algorithms."""
    nodes = [GraphNodeRecord(id=n, label=n, type="t") for n in ("h", "a", "b", "c")]
    edges = [
        GraphEdgeRecord(id="e1", source="a", target="h", type="rel"),
        GraphEdgeRecord(id="e2", source="b", target="h", type="rel"),
        GraphEdgeRecord(id="e3", source="c", target="h", type="rel"),
    ]
    return build_graph(nodes, edges)


def test_degree_centrality_ranks_the_hub_highest():
    graph = _star_graph()

    scores = degree_centrality(graph)

    assert scores["h"] > scores["a"]
    assert scores["h"] > scores["b"]
    assert scores["h"] > scores["c"]


def test_degree_centrality_is_normalized_between_zero_and_one():
    graph = _star_graph()

    scores = degree_centrality(graph)

    assert all(0.0 <= score <= 1.0 for score in scores.values())


def test_degree_centrality_on_empty_graph_returns_empty_scores():
    import networkx as nx

    scores = degree_centrality(nx.DiGraph())

    assert scores == {}


def test_pagerank_ranks_the_hub_highest():
    graph = _inward_star_graph()

    scores = pagerank(graph)

    assert scores["h"] > scores["a"]
    assert scores["h"] > scores["b"]
    assert scores["h"] > scores["c"]
    assert abs(sum(scores.values()) - 1.0) < 1e-6  # pagerank scores sum to 1


def test_betweenness_centrality_ranks_the_bridge_node_highest():
    """Path graph a-h-b: h sits on every shortest path between a and b, so it
    has strictly higher betweenness than the endpoints (which have zero)."""
    nodes = [GraphNodeRecord(id=n, label=n, type="t") for n in ("a", "h", "b")]
    edges = [
        GraphEdgeRecord(id="e1", source="a", target="h", type="rel"),
        GraphEdgeRecord(id="e2", source="h", target="b", type="rel"),
    ]
    graph = build_graph(nodes, edges)

    scores = betweenness_centrality(graph)

    assert scores["h"] > scores["a"]
    assert scores["h"] > scores["b"]
    assert scores["a"] == 0.0
    assert scores["b"] == 0.0


def test_closeness_centrality_ranks_the_hub_highest():
    graph = _inward_star_graph()

    scores = closeness_centrality(graph)

    assert scores["h"] > scores["a"]
    assert scores["h"] > scores["b"]
    assert scores["h"] > scores["c"]
