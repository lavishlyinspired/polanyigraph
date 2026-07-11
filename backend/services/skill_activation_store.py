"""Real, persisted "active skill" state (PLAN.md §10 Skills MCP server's
activate_skill tool). Previously agents/skill_store.py's skills were loaded
fresh per-call with no concept of being active/inactive -- this gives
activate_skill a real, observable effect: a set of currently-active skill
names, persisted in Neo4j, not a stateless no-op.
"""

from __future__ import annotations

from db.neo4j_client import Neo4jClient


def activate_skill(neo4j: Neo4jClient, *, name: str) -> None:
    neo4j.run("MERGE (s:ActiveSkill {name: $name}) SET s.activatedAt = datetime()", name=name)


def deactivate_skill(neo4j: Neo4jClient, *, name: str) -> None:
    neo4j.run("MATCH (s:ActiveSkill {name: $name}) DETACH DELETE s", name=name)


def is_active(neo4j: Neo4jClient, *, name: str) -> bool:
    rows = neo4j.run("MATCH (s:ActiveSkill {name: $name}) RETURN s.name AS name", name=name)
    return len(rows) > 0


def list_active_skills(neo4j: Neo4jClient) -> set[str]:
    rows = neo4j.run("MATCH (s:ActiveSkill) RETURN s.name AS name")
    return {row["name"] for row in rows}
