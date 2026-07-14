"""Graph metrics + weighted pathfinding (PLAN: plans/analytical-engine.md
Slice 4). Fills a gap path_engine.py structurally can't -- its BFS is
label-addressed and unweighted, ignoring GraphEdgeRecord.weight entirely.
path_engine.py itself is untouched; this module is a distinct, id-addressed
capability, not a replacement.

graph_diameter/average_path_length/node_eccentricity all compute on the
largest weakly-connected component when the graph is disconnected, and
report how many other components exist rather than silently ignoring them.
"""

from __future__ import annotations

import networkx as nx


def weighted_shortest_path(graph: nx.DiGraph, source: str, target: str) -> tuple[list[str], float] | None:
    try:
        path = nx.dijkstra_path(graph, source, target, weight="weight")
        length = nx.dijkstra_path_length(graph, source, target, weight="weight")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None
    return path, length


def all_pairs_distances(graph: nx.DiGraph) -> dict[str, dict[str, float]]:
    return dict(nx.all_pairs_dijkstra_path_length(graph, weight="weight"))


def _largest_component_and_disconnected_count(graph: nx.DiGraph) -> tuple[nx.Graph, int]:
    undirected = graph.to_undirected()
    components = list(nx.connected_components(undirected))
    if not components:
        return undirected, 0
    largest = max(components, key=len)
    return undirected.subgraph(largest), len(components) - 1


def graph_diameter(graph: nx.DiGraph) -> tuple[float, int]:
    subgraph, disconnected_count = _largest_component_and_disconnected_count(graph)
    if subgraph.number_of_nodes() <= 1:
        return 0.0, disconnected_count
    return float(nx.diameter(subgraph)), disconnected_count


def average_path_length(graph: nx.DiGraph) -> tuple[float, int]:
    subgraph, disconnected_count = _largest_component_and_disconnected_count(graph)
    if subgraph.number_of_nodes() <= 1:
        return 0.0, disconnected_count
    return nx.average_shortest_path_length(subgraph), disconnected_count


def node_eccentricity(graph: nx.DiGraph) -> tuple[dict[str, float], int]:
    subgraph, disconnected_count = _largest_component_and_disconnected_count(graph)
    if subgraph.number_of_nodes() <= 1:
        return {n: 0.0 for n in subgraph.nodes}, disconnected_count
    return nx.eccentricity(subgraph), disconnected_count
