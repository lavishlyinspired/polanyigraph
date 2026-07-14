"""Unit tests for analytics/algorithms/pathfinding.py (pure, no DB).

Fills the gap path_engine.py structurally can't: weighted shortest path
(path_engine's BFS ignores GraphEdgeRecord.weight entirely) and whole-graph
health metrics. path_engine.py itself is untouched by this slice.
"""

from __future__ import annotations

from analytics.algorithms.pathfinding import (
    all_pairs_distances,
    average_path_length,
    graph_diameter,
    node_eccentricity,
    weighted_shortest_path,
)
from analytics.projection import build_graph
from services.graph_service import GraphEdgeRecord, GraphNodeRecord


def _weighted_diamond():
    """a -> b -> d (weight 1+1=2) is cheaper than the direct a -> d edge
    (weight 10) -- the case path_engine's unweighted BFS gets wrong (BFS
    would prefer the direct single-hop edge)."""
    nodes = [GraphNodeRecord(id=n, label=n, type="t") for n in ("a", "b", "c", "d")]
    edges = [
        GraphEdgeRecord(id="e1", source="a", target="b", type="rel", weight=1.0),
        GraphEdgeRecord(id="e2", source="b", target="d", type="rel", weight=1.0),
        GraphEdgeRecord(id="e3", source="a", target="d", type="rel", weight=10.0),
        GraphEdgeRecord(id="e4", source="a", target="c", type="rel", weight=1.0),
    ]
    return build_graph(nodes, edges)


def test_weighted_shortest_path_prefers_the_cheaper_multi_hop_route():
    graph = _weighted_diamond()

    path, total_weight = weighted_shortest_path(graph, "a", "d")

    assert path == ["a", "b", "d"]
    assert total_weight == 2.0


def test_weighted_shortest_path_returns_none_when_no_path_exists():
    graph = _weighted_diamond()

    result = weighted_shortest_path(graph, "c", "d")

    assert result is None


def test_weighted_shortest_path_returns_none_for_unknown_node():
    graph = _weighted_diamond()

    result = weighted_shortest_path(graph, "a", "does-not-exist")

    assert result is None


def test_all_pairs_distances_reports_correct_weighted_distances():
    graph = _weighted_diamond()

    distances = all_pairs_distances(graph)

    assert distances["a"]["b"] == 1.0
    assert distances["a"]["d"] == 2.0  # via b, not the direct weight-10 edge
    assert "d" not in distances["c"]  # no path from c to anything


def _connected_path_graph():
    """a - b - c - d, unweighted (implicit weight=1.0 default). diameter 3,
    average shortest path length 5/3 (over 6 ordered pairs... actually
    networkx computes it correctly; asserted against known value below)."""
    nodes = [GraphNodeRecord(id=n, label=n, type="t") for n in ("a", "b", "c", "d")]
    edges = [
        GraphEdgeRecord(id="e1", source="a", target="b", type="rel"),
        GraphEdgeRecord(id="e2", source="b", target="c", type="rel"),
        GraphEdgeRecord(id="e3", source="c", target="d", type="rel"),
    ]
    return build_graph(nodes, edges)


def test_graph_diameter_on_a_connected_path_graph():
    graph = _connected_path_graph()

    diameter, disconnected_count = graph_diameter(graph)

    assert diameter == 3
    assert disconnected_count == 0


def test_average_path_length_on_a_connected_path_graph():
    graph = _connected_path_graph()

    avg, disconnected_count = average_path_length(graph)

    assert avg > 0
    assert disconnected_count == 0


def test_node_eccentricity_on_a_connected_path_graph():
    graph = _connected_path_graph()

    ecc, disconnected_count = node_eccentricity(graph)

    assert ecc["a"] == 3  # farthest from d, 3 hops
    assert ecc["b"] == 2
    assert disconnected_count == 0


def test_metrics_computed_on_largest_component_when_disconnected():
    """Path graph a-b-c-d (largest) plus an isolated pair x-y -- metrics
    should reflect the largest component only, with disconnected_count
    reporting the other component instead of silently ignoring it."""
    nodes = [GraphNodeRecord(id=n, label=n, type="t") for n in ("a", "b", "c", "d", "x", "y")]
    edges = [
        GraphEdgeRecord(id="e1", source="a", target="b", type="rel"),
        GraphEdgeRecord(id="e2", source="b", target="c", type="rel"),
        GraphEdgeRecord(id="e3", source="c", target="d", type="rel"),
        GraphEdgeRecord(id="e4", source="x", target="y", type="rel"),
    ]
    graph = build_graph(nodes, edges)

    diameter, disconnected_count = graph_diameter(graph)

    assert diameter == 3  # from the a-b-c-d component, not the x-y pair
    assert disconnected_count == 1  # one other component exists
