"""Custom reasoning rules (Rules Manager add/delete), stored in Neo4j.

Global, not graph-scoped: a rule describes a relationship pattern in the
ontology (e.g. "organization issues security"), which is shared across every
graph built from that ontology, not specific to one document's graph.

Kept separate from the hand-authored seed file (reasoning/rules_repo.py,
data/rules/fibo_rules.json): the seed set is curated and version-controlled;
these are user-added at runtime and deletable.
"""

from __future__ import annotations

from db.neo4j_client import Neo4jClient
from reasoning.engine import Rule
from reasoning.rules_repo import load_rules


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
    the Construct tab really participates in reasoning, not just displayed."""
    return load_rules() + list_custom_rules(neo4j)
