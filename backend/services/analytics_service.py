"""Thin service-layer wrapper around backend/analytics for the agent's
analyst_node (PLAN: plans/analytical-engine.md Slice 9) -- the node calls
this directly, not the HTTP API, matching every other specialist node's
convention (reasoner_node calls reasoning_service, querier_node calls
query_engine, ...). Builds a throwaway, unregistered projection (same
pattern as community_service.py's Slice 3 fix) so ad hoc agent-turn
analysis never leaks entries into the HTTP API's named-projection registry.
"""

from __future__ import annotations

from analytics.projection import build_graph
from analytics.registry import default_registry
from db.neo4j_client import Neo4jClient
from services import graph_service


def run_default_analysis(neo4j: Neo4jClient, graph_id: str, algorithm: str = "degree_centrality") -> dict[str, float]:
    """Returns {} for an empty graph or an unknown algorithm -- callers treat
    that the same way querier_node treats an empty result set, not an error."""
    record = graph_service.get_graph(neo4j, graph_id)
    if not record.nodes:
        return {}
    spec = default_registry.get(algorithm)
    if spec is None:
        return {}
    graph = build_graph(record.nodes, record.edges)
    return spec.func(graph)
