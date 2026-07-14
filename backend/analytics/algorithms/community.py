"""Community detection: pure functions over a networkx.DiGraph (PLAN: plans/
analytical-engine.md Slice 3). Both algorithms return dict[node_id, int] --
same shape as the centrality functions -- rather than the list[set[node]]
networkx itself returns, so callers (community_service.py, the future
registry entry) get one uniform "node -> assignment" contract regardless of
algorithm category.
"""

from __future__ import annotations

import networkx as nx


def louvain_communities(graph: nx.DiGraph, resolution: float = 1.0) -> dict[str, int]:
    undirected = graph.to_undirected()
    communities = nx.algorithms.community.louvain_communities(undirected, resolution=resolution, seed=0)
    return {node: idx for idx, community in enumerate(communities) for node in community}


def weakly_connected_components(graph: nx.DiGraph) -> dict[str, int]:
    components = nx.weakly_connected_components(graph)
    return {node: idx for idx, component in enumerate(components) for node in component}
