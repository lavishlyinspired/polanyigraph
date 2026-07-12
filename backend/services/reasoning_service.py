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
from reasoning.engine import DerivedFact as ReasoningDerivedFact
from reasoning.engine import InferenceTraceEntry, ReasoningResult
from reasoning.engine import feed_back_activation as feed_back_activation_engine
from reasoning.engine import reason as run_reasoning_engine
from reasoning.engine import run_inference as run_inference_engine
from reasoning.engine import spread_activation as spread_activation_engine
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
    # Feature 2 (semantic conditioning at inference, 2026-07-13 plan §4): a
    # rule can type-match by its OWN declared types yet still produce an
    # edge the ontology's real rdfs:domain/rdfs:range never allows -- this
    # is the independent, ontology-level check that catches that case,
    # fails open (returns True) for any property the loaded ontology
    # doesn't describe a domain/range for, so it only ever rejects what the
    # schema itself actually disallows.
    domain_range_check = schema.build_domain_range_matcher()
    result = run_reasoning_engine(
        nodes, edges, rules, resolved_source_id,
        decay=settings.reason_decay,
        epsilon=settings.reason_epsilon,
        max_iterations=settings.reason_max_iterations,
        domain_range_check=domain_range_check,
        type_matches=type_matches,
    )

    graph_service.apply_activation(neo4j, graph_id=graph_id, activation=result.activation)
    graph_service.save_derived_facts(neo4j, graph_id=graph_id, facts=list(result.facts))

    return result


# --- Manual step-by-step mode (Reason tab prototype parity) -----------------
# The prototype lets a user manually trigger Spread Activation / Run
# Inference / Feed Back as three separate steps rather than only the atomic
# run_reasoning() above. Each step here reads whatever's currently persisted
# in Neo4j, calls the same pure engine function run_reasoning() uses
# internally, and persists the result -- so state survives across separate
# HTTP calls, not just one request's lifetime.

def _entity_activation_map(neo4j: Neo4jClient, graph_id: str) -> dict[str, float]:
    record = graph_service.get_graph(neo4j, graph_id)
    return {n.id: (n.activation or 0.0) for n in record.nodes}


def spread_activation_step(
    neo4j: Neo4jClient, graph_id: str, source_id: str | None, *, decay: float,
) -> dict[str, float]:
    """Spread activation from source_id alone, seeded with whatever's already
    persisted (so repeated manual spreads accumulate, matching §8.4's
    persistent-activation design), without running inference or feedback."""
    nodes, edges = graph_service.get_entities_and_edges_for_reasoning(neo4j, graph_id)
    if not nodes:
        raise EmptyGraphError(f"Graph '{graph_id}' has no entities to reason over.")
    resolved_source_id = source_id or _pick_source(nodes)
    if resolved_source_id not in {n.id for n in nodes}:
        raise UnknownSourceError(f"source_id '{resolved_source_id}' not found in graph '{graph_id}'.")

    seed = _entity_activation_map(neo4j, graph_id)
    activation = spread_activation_engine(nodes, edges, resolved_source_id, decay=decay, seed=seed)
    graph_service.apply_activation(neo4j, graph_id=graph_id, activation=activation)
    return activation


def run_inference_step(
    neo4j: Neo4jClient, graphdb: GraphDBClient, settings: Settings, graph_id: str,
) -> tuple[list[ReasoningDerivedFact], list[InferenceTraceEntry]]:
    """Fire rules against whatever activation is currently persisted, without
    spreading first. Facts already derived (by id) don't fire again."""
    nodes, edges = graph_service.get_entities_and_edges_for_reasoning(neo4j, graph_id)
    if not nodes:
        raise EmptyGraphError(f"Graph '{graph_id}' has no entities to reason over.")

    activation = _entity_activation_map(neo4j, graph_id)
    existing = graph_service.get_derived_facts_full(neo4j, graph_id)
    existing_ids = frozenset(f.id for f in existing)
    facts_by_target = {
        f.target_id: ReasoningDerivedFact(
            id=f.id, rule_id=f.rule_id, rule_name=f.rule_name, source_id=f.source_id,
            target_id=f.target_id, fact=f.fact, confidence=f.confidence, iteration=f.iteration,
            proof_path=f.proof_path,
        )
        for f in existing
    }
    iteration = max((f.iteration for f in existing), default=0) + 1

    rules = load_all_rules(neo4j)
    schema = load_schema(graphdb, settings.graphdb_repository)
    type_matches = schema.build_subclass_matcher()

    new_facts, trace = run_inference_engine(
        nodes, edges, rules, activation,
        iteration=iteration, existing_fact_ids=existing_ids, facts_by_target=facts_by_target,
        type_matches=type_matches,
    )
    if new_facts:
        graph_service.save_derived_facts(neo4j, graph_id=graph_id, facts=new_facts)
    return new_facts, trace


def feed_back_step(neo4j: Neo4jClient, graph_id: str, *, feedback_gain: float) -> dict[str, float]:
    """Boost activation on derived facts' targets that haven't been fed back
    yet, then mark them fed back so a second call doesn't double-count."""
    activation = _entity_activation_map(neo4j, graph_id)
    pending = [f for f in graph_service.get_derived_facts_full(neo4j, graph_id) if not f.fed_back]
    if not pending:
        return activation

    facts_for_engine = [
        ReasoningDerivedFact(
            id=f.id, rule_id=f.rule_id, rule_name=f.rule_name, source_id=f.source_id,
            target_id=f.target_id, fact=f.fact, confidence=f.confidence, iteration=f.iteration,
            proof_path=f.proof_path,
        )
        for f in pending
    ]
    boosted = feed_back_activation_engine(activation, facts_for_engine, feedback_gain=feedback_gain)
    graph_service.apply_activation(neo4j, graph_id=graph_id, activation=boosted)
    graph_service.mark_facts_fed_back(neo4j, graph_id=graph_id, fact_ids=[f.id for f in pending])
    return boosted
