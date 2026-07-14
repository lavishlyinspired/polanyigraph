"""Structural (topology-only, shared-neighbor) similarity (PLAN: plans/
analytical-engine.md Slice 5). Deliberately not a deduplication signal --
entity_resolution_service.py already does embedding + label-token
similarity for that, empirically calibrated against real duplicate/
non-duplicate pairs. This answers a different question ("do these nodes
play the same role in the graph"), never used for merge candidates.
"""

from __future__ import annotations

import itertools

import networkx as nx


def jaccard_similarity(graph: nx.DiGraph, node_a: str, node_b: str) -> float:
    undirected = graph.to_undirected()
    _, _, score = next(nx.jaccard_coefficient(undirected, [(node_a, node_b)]))
    return score


def adamic_adar_similarity(graph: nx.DiGraph, node_a: str, node_b: str) -> float:
    undirected = graph.to_undirected()
    _, _, score = next(nx.adamic_adar_index(undirected, [(node_a, node_b)]))
    return score


def similar_node_pairs(graph: nx.DiGraph, threshold: float = 0.5) -> list[tuple[str, str, float]]:
    undirected = graph.to_undirected()
    # nx.jaccard_coefficient consumes ebunch more than once internally -- a
    # generator (e.g. bare itertools.combinations) silently yields zero
    # results with no error, so this must be a materialized list.
    candidate_pairs = list(itertools.combinations(sorted(undirected.nodes), 2))
    return [(u, v, score) for u, v, score in nx.jaccard_coefficient(undirected, candidate_pairs) if score >= threshold]
