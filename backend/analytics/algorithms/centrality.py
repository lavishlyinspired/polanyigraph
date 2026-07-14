"""Centrality algorithms: pure functions over a networkx.DiGraph, no
knowledge of Neo4j, projections, or AlgorithmResult -- the caller (API
layer) wraps the returned dict into an AlgorithmResult once it knows the
projection context (PLAN: plans/analytical-engine.md Slice 1/2).
"""

from __future__ import annotations

import networkx as nx


def degree_centrality(graph: nx.DiGraph) -> dict[str, float]:
    return nx.degree_centrality(graph)


def pagerank(graph: nx.DiGraph, alpha: float = 0.85) -> dict[str, float]:
    return nx.pagerank(graph, alpha=alpha)


def betweenness_centrality(graph: nx.DiGraph) -> dict[str, float]:
    return nx.betweenness_centrality(graph)


def closeness_centrality(graph: nx.DiGraph) -> dict[str, float]:
    return nx.closeness_centrality(graph)
