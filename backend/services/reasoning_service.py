"""Reasoning invocation + persistence (PLAN.md §8.4), extracted from
api/reason.py so the REST endpoint and the LangGraph agent's reasoner node
(backend/agents/graph.py) share one tested implementation instead of two
copies of the same logic.
"""

from __future__ import annotations

from app.config import Settings
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient
from ontology.loader import load_schema
from reasoning.engine import ReasoningResult
from reasoning.engine import reason as run_reasoning_engine
from services import graph_service
from services.rules_store import load_all_rules


class EmptyGraphError(Exception):
    """Raised when graph_id has no entities to reason over."""


class UnknownSourceError(Exception):
    """Raised when source_id doesn't reference a real entity in this graph."""


def _pick_source(nodes) -> str | None:
    """No source given: pick the first node.

    MVP heuristic; a future version can rank by degree or let the UI pick.
    """
    return nodes[0].id if nodes else None


def run_reasoning(
    neo4j: Neo4jClient,
    graphdb: GraphDBClient,
    settings: Settings,
    *,
    graph_id: str,
    source_id: str | None,
) -> ReasoningResult:
    """Runs the persistent-activation loop (§8.4) from source_id (or the
    first node if omitted) and persists activation + derived facts.

    Raises EmptyGraphError if graph_id has no entities, UnknownSourceError
    if source_id was given but doesn't reference a real entity."""
    nodes, edges = graph_service.get_entities_and_edges_for_reasoning(neo4j, graph_id)
    if not nodes:
        raise EmptyGraphError(f"Graph '{graph_id}' has no entities to reason over.")

    resolved_source_id = source_id or _pick_source(nodes)
    if resolved_source_id not in {n.id for n in nodes}:
        raise UnknownSourceError(f"source_id '{resolved_source_id}' not found in graph '{graph_id}'.")

    rules = load_all_rules(neo4j)
    # Ontology-aware matching: rules reference generic ancestor types
    # ("organization") while real extraction returns specific subclasses
    # ("commercial bank") -- see docs/MVP_PLAN.md §12.
    schema = load_schema(graphdb, settings.graphdb_repository)
    type_matches = schema.build_subclass_matcher()
    result = run_reasoning_engine(
        nodes, edges, rules, resolved_source_id,
        decay=settings.reason_decay,
        epsilon=settings.reason_epsilon,
        max_iterations=settings.reason_max_iterations,
        type_matches=type_matches,
    )

    graph_service.apply_activation(neo4j, graph_id=graph_id, activation=result.activation)
    graph_service.save_derived_facts(neo4j, graph_id=graph_id, facts=list(result.facts))

    return result
