"""Unit tests for analytics/algorithms/community.py (pure, no DB)."""

from __future__ import annotations

from analytics.algorithms.community import louvain_communities, weakly_connected_components
from analytics.projection import build_graph
from services.graph_service import GraphEdgeRecord, GraphNodeRecord


def _two_disjoint_triangles():
    """Two fully-connected triangles (a1-a2-a3, b1-b2-b3) with no edges
    between them -- the textbook case both algorithms must separate."""
    nodes = [GraphNodeRecord(id=n, label=n, type="t") for n in ("a1", "a2", "a3", "b1", "b2", "b3")]
    edges = [
        GraphEdgeRecord(id="e1", source="a1", target="a2", type="rel"),
        GraphEdgeRecord(id="e2", source="a2", target="a3", type="rel"),
        GraphEdgeRecord(id="e3", source="a3", target="a1", type="rel"),
        GraphEdgeRecord(id="e4", source="b1", target="b2", type="rel"),
        GraphEdgeRecord(id="e5", source="b2", target="b3", type="rel"),
        GraphEdgeRecord(id="e6", source="b3", target="b1", type="rel"),
    ]
    return build_graph(nodes, edges)


def test_louvain_communities_separates_two_disconnected_clusters():
    graph = _two_disjoint_triangles()

    assignments = louvain_communities(graph)

    a_communities = {assignments["a1"], assignments["a2"], assignments["a3"]}
    b_communities = {assignments["b1"], assignments["b2"], assignments["b3"]}
    assert len(a_communities) == 1
    assert len(b_communities) == 1
    assert a_communities != b_communities


def test_louvain_communities_covers_every_node():
    graph = _two_disjoint_triangles()

    assignments = louvain_communities(graph)

    assert set(assignments) == set(graph.nodes)


def test_louvain_communities_is_invariant_to_edge_direction():
    """Real edge direction reflects an arbitrary extraction/parsing choice
    ("Acme Corp owns Acme Holdings" vs "Acme Holdings is owned by Acme
    Corp") -- community structure must not flip depending on which way a
    relationship happened to be phrased. networkx's louvain_communities has
    genuinely different directed and undirected modularity formulas (it does
    NOT silently ignore direction), so this must be explicit, not assumed."""
    forward = _two_disjoint_triangles()

    nodes = [GraphNodeRecord(id=n, label=n, type="t") for n in ("a1", "a2", "a3", "b1", "b2", "b3")]
    reversed_edges = [
        GraphEdgeRecord(id="e1", source="a2", target="a1", type="rel"),
        GraphEdgeRecord(id="e2", source="a3", target="a2", type="rel"),
        GraphEdgeRecord(id="e3", source="a1", target="a3", type="rel"),
        GraphEdgeRecord(id="e4", source="b2", target="b1", type="rel"),
        GraphEdgeRecord(id="e5", source="b3", target="b2", type="rel"),
        GraphEdgeRecord(id="e6", source="b1", target="b3", type="rel"),
    ]
    reversed_graph = build_graph(nodes, reversed_edges)

    forward_assignments = louvain_communities(forward)
    reversed_assignments = louvain_communities(reversed_graph)

    # Same grouping of nodes into communities, independent of edge direction
    # (community *labels*/indices may legitimately differ, membership must not).
    def _groups(assignments):
        by_group: dict[int, set[str]] = {}
        for node, group in assignments.items():
            by_group.setdefault(group, set()).add(node)
        return set(frozenset(g) for g in by_group.values())

    assert _groups(forward_assignments) == _groups(reversed_assignments)


def test_weakly_connected_components_separates_two_disconnected_clusters():
    graph = _two_disjoint_triangles()

    assignments = weakly_connected_components(graph)

    a_components = {assignments["a1"], assignments["a2"], assignments["a3"]}
    b_components = {assignments["b1"], assignments["b2"], assignments["b3"]}
    assert len(a_components) == 1
    assert len(b_components) == 1
    assert a_components != b_components


def test_weakly_connected_components_follows_edges_regardless_of_direction():
    """a -> b, c -> b: directed, no path a->c or c->a, but weakly connected
    (undirected view) they're all one component."""
    nodes = [GraphNodeRecord(id=n, label=n, type="t") for n in ("a", "b", "c")]
    edges = [
        GraphEdgeRecord(id="e1", source="a", target="b", type="rel"),
        GraphEdgeRecord(id="e2", source="c", target="b", type="rel"),
    ]
    graph = build_graph(nodes, edges)

    assignments = weakly_connected_components(graph)

    assert assignments["a"] == assignments["b"] == assignments["c"]
