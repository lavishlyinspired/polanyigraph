"""Unit tests for analytics/algorithms/similarity.py (pure, no DB).

Topology-only structural similarity (shared neighbors) -- deliberately not
used for entity deduplication, which is entity_resolution_service.py's job
(embedding + label-token similarity, empirically calibrated). No code path
is shared between the two; this is a different question ("do these nodes
play the same role in the graph") answered a different way.
"""

from __future__ import annotations

from analytics.algorithms.similarity import adamic_adar_similarity, jaccard_similarity, similar_node_pairs
from analytics.projection import build_graph
from services.graph_service import GraphEdgeRecord, GraphNodeRecord


def _shared_neighbor_graph():
    """a and b share 2 of 3 combined neighbors (x, y common; b alone has z)
    -- jaccard(a, b) = 2/3. c has no edges at all."""
    nodes = [GraphNodeRecord(id=n, label=n, type="t") for n in ("a", "b", "c", "x", "y", "z")]
    edges = [
        GraphEdgeRecord(id="e1", source="a", target="x", type="rel"),
        GraphEdgeRecord(id="e2", source="a", target="y", type="rel"),
        GraphEdgeRecord(id="e3", source="b", target="x", type="rel"),
        GraphEdgeRecord(id="e4", source="b", target="y", type="rel"),
        GraphEdgeRecord(id="e5", source="b", target="z", type="rel"),
    ]
    return build_graph(nodes, edges)


def test_jaccard_similarity_of_nodes_with_shared_neighbors():
    graph = _shared_neighbor_graph()

    score = jaccard_similarity(graph, "a", "b")

    assert abs(score - 2 / 3) < 1e-9


def test_jaccard_similarity_is_bounded_between_zero_and_one():
    graph = _shared_neighbor_graph()

    for pair in [("a", "b"), ("a", "c"), ("b", "c")]:
        score = jaccard_similarity(graph, *pair)
        assert 0.0 <= score <= 1.0


def test_jaccard_similarity_of_a_node_with_no_neighbors_is_zero():
    graph = _shared_neighbor_graph()

    score = jaccard_similarity(graph, "c", "a")

    assert score == 0.0


def test_adamic_adar_similarity_of_nodes_with_shared_neighbors_is_positive():
    graph = _shared_neighbor_graph()

    score = adamic_adar_similarity(graph, "a", "b")

    assert score > 0.0


def test_adamic_adar_similarity_of_a_node_with_no_neighbors_is_zero():
    graph = _shared_neighbor_graph()

    score = adamic_adar_similarity(graph, "c", "a")

    assert score == 0.0


def test_similar_node_pairs_returns_pairs_above_threshold():
    graph = _shared_neighbor_graph()

    pairs = similar_node_pairs(graph, threshold=0.5)

    matched = {(u, v) for u, v, _score in pairs} | {(v, u) for u, v, _score in pairs}
    assert ("a", "b") in matched
    assert all(score >= 0.5 for _u, _v, score in pairs)


def test_similar_node_pairs_includes_a_pair_exactly_at_threshold():
    """threshold is inclusive: jaccard(a, b) == 2/3 exactly, threshold == 2/3
    exactly -- must be included (boundary, catches > vs >=)."""
    graph = _shared_neighbor_graph()

    pairs = similar_node_pairs(graph, threshold=2 / 3)

    matched = {(u, v) for u, v, _score in pairs} | {(v, u) for u, v, _score in pairs}
    assert ("a", "b") in matched


def test_similar_node_pairs_excludes_pairs_below_threshold():
    graph = _shared_neighbor_graph()

    pairs = similar_node_pairs(graph, threshold=0.9)

    matched = {(u, v) for u, v, _score in pairs} | {(v, u) for u, v, _score in pairs}
    assert ("a", "b") not in matched  # 2/3 < 0.9
