"""General-purpose key/value preferences store (PLAN.md §10 Memory MCP
server's save_preference tool). Global, not graph-scoped -- an app-level
setting (e.g. "default_repository") is shared across graphs, same
convention as services/rules_store.py's custom rules. No preferences
mechanism existed before this.
"""

from __future__ import annotations

from dataclasses import dataclass

from db.neo4j_client import Neo4jClient


@dataclass(frozen=True)
class PreferenceRecord:
    key: str
    value: str


def save_preference(neo4j: Neo4jClient, *, key: str, value: str) -> None:
    neo4j.run(
        "MERGE (p:Preference {key: $key}) SET p.value = $value, p.updatedAt = datetime()",
        key=key, value=value,
    )


def get_preference(neo4j: Neo4jClient, *, key: str) -> str | None:
    rows = neo4j.run("MATCH (p:Preference {key: $key}) RETURN p.value AS value", key=key)
    return rows[0]["value"] if rows else None


def list_preferences(neo4j: Neo4jClient) -> list[PreferenceRecord]:
    rows = neo4j.run("MATCH (p:Preference) RETURN p.key AS key, p.value AS value ORDER BY p.key")
    return [PreferenceRecord(key=row["key"], value=row["value"]) for row in rows]


def delete_preference(neo4j: Neo4jClient, *, key: str) -> None:
    neo4j.run("MATCH (p:Preference {key: $key}) DETACH DELETE p", key=key)
