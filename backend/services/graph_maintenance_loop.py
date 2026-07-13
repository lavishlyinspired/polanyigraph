"""Autonomous graph maintenance loop (2026-07-13 plan §12.3, Feature 7):
periodic upkeep over a graph's own data -- mining new rule candidates,
running reasoning to convergence, backstopping entity-resolution checks,
and reporting current rule-review state. "Maker" only: every lasting
output lands on an EXISTING human-approval gate this project already
built (Feature 3's :CandidateRule, Feature 6's :DuplicateCandidate) --
this loop never auto-applies anything a human hasn't already been asked
to review. The "checker" is that same existing human-gate mechanism, not
a second LLM grading the first one's work (plan's own framing).

Honest scope note on cadence: the plan references
`mcp__scheduled-tasks__create_scheduled_task` for triggering runs
(nightly, or after N new documents). No such MCP server or scheduling
infrastructure exists anywhere in this codebase (checked: no cron/
APScheduler/task-queue code anywhere). This module provides the real,
testable maintenance logic plus a REST endpoint to trigger one run
manually (api/graph_maintenance.py) -- wiring an actual periodic trigger
(a real cron job hitting that endpoint, an external task queue, etc.) is
a deployment decision left to whoever operates this, not invented here.

Honest note on the "L1-safe by construction" claim (2026-07-13 checklist):
true for steps 1 (mining) and 3 (entity resolution) below -- both only
ever create a *candidate* record awaiting human approval, never a
structural graph change. It's more nuanced for step 2 (reasoning):
:DerivedFact creation was ALREADY gate-free before this feature existed
(services/chat_service.py reads get_derived_facts() -- every derived
fact, no review-status filter -- for chat grounding) -- Feature 5's
review is a real, working mechanism that adjusts a rule's *future*
weight, not a pre-use gate on the *current* fact. Feature 7 doesn't
change that risk profile; it runs the exact same already-accepted
run_reasoning operation on a schedule instead of on-demand, so it
introduces no NEW auto-apply behavior beyond what already existed.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field

from app.config import Settings
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient
from ontology.loader import load_schema
from services import entity_resolution_service, graph_service, reasoning_service, rule_mining_service, rules_store


@dataclass(frozen=True)
class LoopRunSummary:
    id: str
    graph_id: str
    mined_candidate_ids: tuple[str, ...] = field(default=())
    reasoning_ran: bool = False
    reasoning_iterations: int | None = None
    reasoning_new_facts: int = 0
    reasoning_converged_by: str | None = None
    duplicate_candidate_ids: tuple[str, ...] = field(default=())
    active_rule_weights: dict[str, float] = field(default_factory=dict)

    def as_summary_text(self) -> str:
        """Human-readable one-liner, matching the plan's own example format:
        "mined 3 candidates ..., reasoning converged after 4 iterations
        with 2 new facts, flagged 1 likely-duplicate entity ..."."""
        parts = [f"mined {len(self.mined_candidate_ids)} rule candidate(s)"]
        if self.reasoning_ran:
            parts.append(f"reasoning converged ({self.reasoning_converged_by}) after {self.reasoning_iterations} iteration(s) with {self.reasoning_new_facts} new fact(s)")
        else:
            parts.append("reasoning skipped (empty graph)")
        parts.append(f"flagged {len(self.duplicate_candidate_ids)} likely-duplicate entity candidate(s)")
        if self.active_rule_weights:
            weights = ", ".join(f"{rid}={w:.2f}" for rid, w in sorted(self.active_rule_weights.items()))
            parts.append(f"active rule weights: {weights}")
        return "; ".join(parts)


def run_maintenance_loop(neo4j: Neo4jClient, graphdb: GraphDBClient, settings: Settings, graph_id: str) -> LoopRunSummary:
    """One maintenance pass over graph_id. Idempotent-safe to re-run: every
    step below (mining, entity resolution) already MERGEs on a
    deterministic id, so re-running never duplicates a candidate or
    resurfaces one a human already rejected."""
    # Step 1 (Maker): mine rule candidates (Feature 3) -- creates :CandidateRule
    # nodes awaiting human approval, never a real, firing :Rule directly.
    candidates = rule_mining_service.mine_candidates(neo4j, graph_id)

    # Step 2 (Maker): run reasoning to convergence (§12.1's already-built
    # /goal loop) -- skipped gracefully for a graph with no entities yet,
    # not an error condition for a maintenance pass.
    try:
        result = reasoning_service.run_reasoning(neo4j, graphdb, settings, graph_id=graph_id, source_id=None)
        reasoning_ran = True
        reasoning_iterations = result.iterations
        reasoning_new_facts = len(result.facts)
        reasoning_converged_by = result.converged_by
        fired_rule_ids = {f.rule_id for f in result.facts}
    except reasoning_service.EmptyGraphError:
        reasoning_ran = False
        reasoning_iterations = None
        reasoning_new_facts = 0
        reasoning_converged_by = None
        fired_rule_ids = set()

    # Step 3 (Maker): entity-resolution backstop (Feature 6) over every real
    # (non-derived) entity in the graph -- a genuine re-check, not
    # redundant with ingest-time checking: entities can enter the graph
    # via paths that never call check_for_duplicate (e.g. POST
    # /graph/{graph_id}/nodes, a manual add), so this is the safety net
    # for those. Same ontology-aware type matching ingest_service.py uses.
    schema = load_schema(graphdb, settings.graphdb_repository)
    type_matches = schema.build_subclass_matcher()
    record = graph_service.get_graph(neo4j, graph_id)
    duplicate_candidate_ids = []
    for node in record.nodes:
        if node.derived:
            continue  # a reasoning-derived fact target, not a real extracted entity to dedup-check
        candidate_id = entity_resolution_service.check_for_duplicate(
            neo4j, graph_id=graph_id, entity_id=node.id, entity_label=node.label, entity_type=node.type,
            type_matches=type_matches,
        )
        if candidate_id is not None:
            duplicate_candidate_ids.append(candidate_id)

    # Step 4 (report only): Feature 5's update_rule_weight already runs
    # SYNCHRONOUSLY at the moment a human reviews a derived fact
    # (reasoning_service.review_derived_fact), not deferred to a batch --
    # so there's no backlog for this step to process. Reports the current
    # weight of whatever rules fired in this run's reasoning pass instead
    # of recomputing anything.
    active_rule_weights = {
        r.id: r.weight for r in rules_store.load_all_rules(neo4j) if r.id in fired_rule_ids
    }

    summary = LoopRunSummary(
        id=f"loop-{graph_id}-{uuid.uuid4().hex[:12]}",
        graph_id=graph_id,
        mined_candidate_ids=tuple(c.id for c in candidates),
        reasoning_ran=reasoning_ran,
        reasoning_iterations=reasoning_iterations,
        reasoning_new_facts=reasoning_new_facts,
        reasoning_converged_by=reasoning_converged_by,
        duplicate_candidate_ids=tuple(duplicate_candidate_ids),
        active_rule_weights=active_rule_weights,
    )
    _persist_loop_run(neo4j, summary)
    return summary


def _persist_loop_run(neo4j: Neo4jClient, summary: LoopRunSummary) -> None:
    """State: a real, queryable :LoopRun Neo4j node -- not a flat
    GRAPH_LOOP_STATE.md file (the plan's other offered option). Chosen for
    consistency with every other piece of review/audit state this project
    tracks (:ImplicitFact, :CandidateRule, :DuplicateCandidate,
    :RuleReviewOutcome all live in Neo4j, none in a markdown file), and so
    it's queryable via REST/UI and testable with this project's real-
    Neo4j-no-mocks convention, unlike a flat file."""
    neo4j.run(
        """
        CREATE (l:LoopRun {
            id: $id, graphId: $graph_id, ranAt: datetime(),
            minedCandidateIds: $mined_candidate_ids,
            reasoningRan: $reasoning_ran, reasoningIterations: $reasoning_iterations,
            reasoningNewFacts: $reasoning_new_facts, reasoningConvergedBy: $reasoning_converged_by,
            duplicateCandidateIds: $duplicate_candidate_ids,
            activeRuleWeightsJson: $active_rule_weights_json,
            summaryText: $summary_text
        })
        """,
        id=summary.id, graph_id=summary.graph_id,
        mined_candidate_ids=list(summary.mined_candidate_ids),
        reasoning_ran=summary.reasoning_ran, reasoning_iterations=summary.reasoning_iterations,
        reasoning_new_facts=summary.reasoning_new_facts, reasoning_converged_by=summary.reasoning_converged_by,
        duplicate_candidate_ids=list(summary.duplicate_candidate_ids),
        active_rule_weights_json=json.dumps(summary.active_rule_weights),
        summary_text=summary.as_summary_text(),
    )


def list_loop_runs(neo4j: Neo4jClient, graph_id: str) -> list[LoopRunSummary]:
    rows = neo4j.run(
        """
        MATCH (l:LoopRun {graphId: $graph_id})
        RETURN l.id AS id, l.graphId AS graphId, l.minedCandidateIds AS minedCandidateIds,
               l.reasoningRan AS reasoningRan, l.reasoningIterations AS reasoningIterations,
               l.reasoningNewFacts AS reasoningNewFacts, l.reasoningConvergedBy AS reasoningConvergedBy,
               l.duplicateCandidateIds AS duplicateCandidateIds, l.activeRuleWeightsJson AS activeRuleWeightsJson,
               l.summaryText AS summaryText
        ORDER BY l.ranAt DESC
        """,
        graph_id=graph_id,
    )
    return [
        LoopRunSummary(
            id=r["id"], graph_id=r["graphId"], mined_candidate_ids=tuple(r["minedCandidateIds"]),
            reasoning_ran=r["reasoningRan"], reasoning_iterations=r["reasoningIterations"],
            reasoning_new_facts=r["reasoningNewFacts"], reasoning_converged_by=r["reasoningConvergedBy"],
            duplicate_candidate_ids=tuple(r["duplicateCandidateIds"]),
            active_rule_weights=json.loads(r["activeRuleWeightsJson"]),
        )
        for r in rows
    ]
