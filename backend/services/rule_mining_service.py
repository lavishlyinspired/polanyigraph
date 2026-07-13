"""Rule mining (2026-07-13 plan §5): finds which (edge_type, source_type,
target_type) combinations already occur often and consistently enough in a
graph's real extracted data to deserve becoming a scored, watchable Rule --
automating what a human currently does by hand-authoring
data/rules/fibo_rules.json entries. Domain-agnostic by construction: reads
whatever node/edge types the currently-loaded ontology produced, no
FIBO-specific code here.

Corrected scope (see plan's own note): this does NOT compose two different
relations into a new inferred one -- reasoning/engine.py's Rule watches a
single (edge_type, source_type, target_type) combination and confirms an
*existing* edge, so "mining a rule" here means finding which combinations
already occur often enough to deserve becoming one, not discovering new
relation types. A true two-relation composition miner is real future work,
deliberately out of scope (would require extending Rule with a body pattern
and run_inference to create new edges, a bigger engine change).

approve_candidate calls the existing, already-tested rules_store.create_rule
-- the exact function the Construct tab already uses for user-added rules --
so nothing about reasoning/engine.py's firing behavior changes for anything
except newly-approved rules; a mined-and-approved rule is indistinguishable
from one a human typed in by hand.

2026-07-13 plan §12.2: pending/approved/rejected :CandidateRule status is
this feature's instance of the same "Human Gate" pattern enrichment's
:ImplicitFact review already uses (services/enrichment_service.py) --
nothing mined here ever auto-promotes to a real, firing Rule without an
explicit human approve_candidate call.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from db.neo4j_client import Neo4jClient
from reasoning.engine import Edge, Node
from services import graph_service, rules_store

_VALID_STATUSES = {"pending", "approved", "rejected"}


@dataclass(frozen=True)
class CandidateRule:
    id: str
    edge_type: str
    source_type: str
    target_type: str
    support: int
    confidence: float
    status: str = "pending"


def _candidate_id(edge_type: str, source_type: str, target_type: str) -> str:
    return f"cand-{edge_type}-{source_type}-{target_type}"


def _mine(nodes: list[Node], edges: list[Edge], *, min_support: int, min_confidence: float) -> list[CandidateRule]:
    by_id = {n.id: n for n in nodes}
    # Count occurrences of each (edge_type, source_type, target_type) combo --
    # avoids proposing rules for edge types that appeared once or twice.
    combo_counts: Counter[tuple[str, str, str]] = Counter()
    for e in edges:
        src, tgt = by_id.get(e.source), by_id.get(e.target)
        if src is None or tgt is None:
            continue
        combo_counts[(e.type, src.type, tgt.type)] += 1

    candidates = []
    for (edge_type, source_type, target_type), support in combo_counts.items():
        if support < min_support:
            continue
        # confidence proxy: fraction of ALL edges out of source_type-typed
        # nodes that are this specific edge_type -- "when a source_type node
        # has an outgoing edge, how often is it this kind."
        total_out_of_source_type = sum(c for (et, st, tt), c in combo_counts.items() if st == source_type)
        confidence = support / total_out_of_source_type if total_out_of_source_type else 0.0
        if confidence < min_confidence:
            continue
        candidates.append(
            CandidateRule(
                id=_candidate_id(edge_type, source_type, target_type),
                edge_type=edge_type, source_type=source_type, target_type=target_type,
                support=support, confidence=confidence,
            )
        )
    return sorted(candidates, key=lambda c: -c.confidence)


def _rejected_combos(neo4j: Neo4jClient) -> set[tuple[str, str, str]]:
    rows = neo4j.run("MATCH (c:CandidateRule {status: 'rejected'}) RETURN c.edgeType AS edgeType, c.sourceType AS sourceType, c.targetType AS targetType")
    return {(r["edgeType"], r["sourceType"], r["targetType"]) for r in rows}


def _persist_candidates(neo4j: Neo4jClient, graph_id: str, candidates: list[CandidateRule]) -> None:
    for c in candidates:
        neo4j.run(
            """
            MERGE (cand:CandidateRule {id: $id})
            ON CREATE SET cand.status = 'pending'
            SET cand.edgeType = $edge_type, cand.sourceType = $source_type, cand.targetType = $target_type,
                cand.support = $support, cand.confidence = $confidence, cand.graphId = $graph_id,
                cand.minedAt = datetime()
            """,
            id=c.id, edge_type=c.edge_type, source_type=c.source_type, target_type=c.target_type,
            support=c.support, confidence=c.confidence, graph_id=graph_id,
        )


def mine_candidates(
    neo4j: Neo4jClient, graph_id: str, *, min_support: int = 3, min_confidence: float = 0.6,
) -> list[CandidateRule]:
    """Mines graph_id's real extracted data for repeating (edge_type,
    source_type, target_type) patterns, persists them as :CandidateRule
    nodes (MERGE-safe, re-running doesn't duplicate), and returns the ones
    not already covered by an existing seed/custom Rule or a previously
    rejected candidate for the same combo."""
    nodes, edges = graph_service.get_entities_and_edges_for_reasoning(neo4j, graph_id)
    existing = {(r.edge_type, r.source_type, r.target_type) for r in rules_store.load_all_rules(neo4j)}
    excluded = existing | _rejected_combos(neo4j)
    candidates = [
        c for c in _mine(nodes, edges, min_support=min_support, min_confidence=min_confidence)
        if (c.edge_type, c.source_type, c.target_type) not in excluded
    ]
    _persist_candidates(neo4j, graph_id, candidates)
    return candidates


def list_candidates(neo4j: Neo4jClient, *, status: str = "pending") -> list[CandidateRule]:
    rows = neo4j.run(
        """
        MATCH (c:CandidateRule {status: $status})
        RETURN c.id AS id, c.edgeType AS edgeType, c.sourceType AS sourceType, c.targetType AS targetType,
               c.support AS support, c.confidence AS confidence, c.status AS status
        ORDER BY c.confidence DESC
        """,
        status=status,
    )
    return [_row_to_candidate(r) for r in rows]


def _get_candidate(neo4j: Neo4jClient, candidate_id: str) -> CandidateRule:
    rows = neo4j.run(
        """
        MATCH (c:CandidateRule {id: $id})
        RETURN c.id AS id, c.edgeType AS edgeType, c.sourceType AS sourceType, c.targetType AS targetType,
               c.support AS support, c.confidence AS confidence, c.status AS status
        """,
        id=candidate_id,
    )
    if not rows:
        raise ValueError(f"No candidate rule '{candidate_id}'.")
    return _row_to_candidate(rows[0])


def _row_to_candidate(row: dict) -> CandidateRule:
    return CandidateRule(
        id=row["id"], edge_type=row["edgeType"], source_type=row["sourceType"], target_type=row["targetType"],
        support=row["support"], confidence=row["confidence"], status=row["status"],
    )


def _set_status(neo4j: Neo4jClient, candidate_id: str, status: str) -> None:
    if status not in _VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}' -- must be one of {_VALID_STATUSES}.")
    neo4j.run("MATCH (c:CandidateRule {id: $id}) SET c.status = $status", id=candidate_id, status=status)


def approve_candidate(neo4j: Neo4jClient, candidate_id: str) -> None:
    """Promotes a candidate to a real, reasoning-participating Rule via the
    same rules_store.create_rule the Construct tab uses -- the mined
    confidence becomes the rule's starting weight, the only "learned" number
    in this feature, and it's a plain frequency ratio, not a trained
    parameter."""
    c = _get_candidate(neo4j, candidate_id)
    rules_store.create_rule(
        neo4j, rule_id=f"mined-{candidate_id}", name=f"Mined: {c.edge_type}",
        edge_type=c.edge_type, source_type=c.source_type, target_type=c.target_type,
        threshold=0.3,  # same default as hand-authored rules; tunable later via Construct tab, same as any custom rule
        weight=c.confidence,
        description="{source} " + c.edge_type + " {target} (mined, support=" + str(c.support) + ")",
    )
    _set_status(neo4j, candidate_id, "approved")


def reject_candidate(neo4j: Neo4jClient, candidate_id: str) -> None:
    """Kept, not deleted, so a later mine_candidates() run doesn't re-surface it."""
    _set_status(neo4j, candidate_id, "rejected")
