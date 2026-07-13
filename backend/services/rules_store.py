"""Custom reasoning rules (Rules Manager add/delete), stored in Neo4j.

Global, not graph-scoped: a rule describes a relationship pattern in the
ontology (e.g. "organization issues security"), which is shared across every
graph built from that ontology, not specific to one document's graph.

Kept separate from the hand-authored seed file (reasoning/rules_repo.py,
data/rules/fibo_rules.json): the seed set is curated and version-controlled;
these are user-added at runtime and deletable.
"""

from __future__ import annotations

import uuid

from db.neo4j_client import Neo4jClient
from reasoning.engine import Rule
from reasoning.rules_repo import load_rules

_VALID_OUTCOMES = {"confirmed", "rejected"}


def create_rule(
    neo4j: Neo4jClient,
    *,
    rule_id: str,
    name: str,
    edge_type: str,
    source_type: str,
    target_type: str,
    threshold: float,
    weight: float,
    description: str,
) -> None:
    neo4j.run(
        """
        MERGE (r:Rule {id: $rule_id})
        SET r.name = $name, r.edgeType = $edge_type,
            r.sourceType = $source_type, r.targetType = $target_type,
            r.threshold = $threshold, r.weight = $weight, r.description = $description
        """,
        rule_id=rule_id, name=name, edge_type=edge_type,
        source_type=source_type, target_type=target_type,
        threshold=threshold, weight=weight, description=description,
    )


def list_custom_rules(neo4j: Neo4jClient) -> list[Rule]:
    rows = neo4j.run(
        """
        MATCH (r:Rule)
        RETURN r.id AS id, r.name AS name, r.edgeType AS edgeType,
               r.sourceType AS sourceType, r.targetType AS targetType,
               r.threshold AS threshold, r.weight AS weight, r.description AS description
        """
    )
    return [
        Rule(
            id=row["id"], name=row["name"], edge_type=row["edgeType"],
            source_type=row["sourceType"], target_type=row["targetType"],
            threshold=row["threshold"], weight=row["weight"], description=row["description"],
        )
        for row in rows
    ]


def delete_rule(neo4j: Neo4jClient, rule_id: str) -> bool:
    rows = neo4j.run("MATCH (r:Rule {id: $rule_id}) DETACH DELETE r RETURN count(r) AS deleted", rule_id=rule_id)
    return bool(rows and rows[0]["deleted"] > 0)


def load_all_rules(neo4j: Neo4jClient) -> list[Rule]:
    """Seed (hand-authored, non-deletable) + custom (user-added) rules,
    combined -- this is what the reasoner actually uses, so a rule added via
    the Construct tab really participates in reasoning, not just displayed.

    A Neo4j-stored rule with the SAME id as a seed rule OVERRIDES it rather
    than adding a second, duplicate entry (2026-07-13 plan §11.1: Feature
    5's rule-weight review needs to update a seed rule's weight too, and
    seed rules are read-only JSON -- update_rule_weight below stores the
    override as a normal :Rule node with the seed rule's own id). Without
    this override semantics, a reviewed seed rule would fire TWICE in
    run_inference (once at its stale seed weight, once at its updated
    Neo4j weight), corrupting Feature 1's noisy-OR aggregation with a
    spurious "second corroborating rule" that's really the same rule
    counted twice."""
    by_id = {r.id: r for r in load_rules()}
    by_id.update({r.id: r for r in list_custom_rules(neo4j)})
    return list(by_id.values())


def update_rule_weight(neo4j: Neo4jClient, rule_id: str, *, outcome: str) -> float:
    """2026-07-13 plan §11.1: every :DerivedFact a rule produces can be
    explicitly confirmed or rejected by a human (see
    reasoning_service.review_derived_fact) -- this is the reward-signal
    update that results in, a rolling-average recompute over ALL recorded
    outcomes structurally identical to the skill graph's record_skill_usage
    (services/skill_graph_service.py), just writing to Rule.weight instead
    of Skill.confidence. Deliberately the same plain rolling average, not a
    bandit -- Feature 0 Stage B (the bandit upgrade) was deliberately not
    built yet (no real usage history to justify it pre-launch); if it ever
    ships, this should share that same upgraded math rather than duplicate
    it (plan's own stated sequencing).

    reasoning/engine.py needs no change at all: it already reads whatever
    load_all_rules() returns, so a weight that moved from review outcomes
    is indistinguishable to the engine from one a human hand-set."""
    if outcome not in _VALID_OUTCOMES:
        raise ValueError(f"Invalid outcome '{outcome}' -- must be one of {_VALID_OUTCOMES}.")
    current = next((r for r in load_all_rules(neo4j) if r.id == rule_id), None)
    if current is None:
        raise ValueError(f"No rule '{rule_id}'.")
    neo4j.run(
        """
        MERGE (r:Rule {id: $rule_id})
        ON CREATE SET r.name = $name, r.edgeType = $edge_type, r.sourceType = $source_type,
                       r.targetType = $target_type, r.threshold = $threshold, r.description = $description,
                       r.weight = $weight
        """,
        rule_id=rule_id, name=current.name, edge_type=current.edge_type,
        source_type=current.source_type, target_type=current.target_type,
        threshold=current.threshold, description=current.description, weight=current.weight,
    )
    neo4j.run(
        "CREATE (o:RuleReviewOutcome {id: $outcome_id, ruleId: $rule_id, outcome: $outcome, reviewedAt: datetime()})",
        outcome_id=f"review-{uuid.uuid4().hex[:12]}", rule_id=rule_id, outcome=outcome,
    )
    rows = neo4j.run(
        """
        MATCH (o:RuleReviewOutcome {ruleId: $rule_id})
        WITH avg(CASE WHEN o.outcome = 'confirmed' THEN 1.0 ELSE 0.0 END) AS newWeight
        MATCH (r:Rule {id: $rule_id})
        SET r.weight = newWeight
        RETURN newWeight
        """,
        rule_id=rule_id,
    )
    return rows[0]["newWeight"]
