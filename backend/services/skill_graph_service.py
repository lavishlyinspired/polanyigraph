"""Neo4j-backed skill graph (PLAN.md §18 / §2.9.14): stores real runtime
skill metadata as first-class graph entities instead of a flat filesystem
list, so discovery can be relationship-aware ("what does this skill
require") and usage-aware (confidence learned from real outcomes, not
hand-tuned). Skill *content* still lives in backend/skills/*/SKILL.md
(agents/skill_store.py) -- this only stores metadata + relationships +
usage history, per the project's "runtime skills are files, loaded fresh"
convention; nothing here duplicates SKILL.md bodies into Neo4j.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from agents import skill_store
from db.neo4j_client import Neo4jClient

# Genuine prerequisites, not invented ones: both enrichment and reasoning
# operate on entities/edges that must already exist in the graph, which only
# extraction produces. kg-query and kg-visualization read existing graph
# state too, but neither *requires* a specific upstream skill to have run in
# the same sense (they format/describe whatever is already there, including
# nothing).
_REQUIRES_EDGES = [
    ("polanyi-enrichment", "kg-extraction"),
    ("neurosymbolic-reasoning", "kg-extraction"),
]

_SCHEMA_STATEMENTS = [
    "CREATE CONSTRAINT skill_name_unique IF NOT EXISTS FOR (s:Skill) REQUIRE s.name IS UNIQUE",
    "CREATE FULLTEXT INDEX skill_description_index IF NOT EXISTS FOR (s:Skill) ON EACH [s.description, s.name]",
]


@dataclass(frozen=True)
class SkillMatch:
    name: str
    description: str
    confidence: float
    score: float
    requires: list[str]


def ensure_schema(neo4j: Neo4jClient) -> None:
    """Idempotent: safe to call on every backend startup, same convention as
    ontology.sync.ensure_constraints."""
    for statement in _SCHEMA_STATEMENTS:
        neo4j.run(statement)


def seed_skills(neo4j: Neo4jClient) -> None:
    """MERGEs a :Skill node per real runtime skill discovered under
    backend/skills/ (agents/skill_store.scan(), the same Discovery pass the
    LangGraph agent itself uses) plus the genuine REQUIRES prerequisites
    above. Idempotent -- MERGE, not CREATE."""
    for meta in skill_store.scan():
        neo4j.run(
            """
            MERGE (s:Skill {name: $name})
            ON CREATE SET s.createdAt = datetime(), s.confidence = 1.0
            SET s.description = $description,
                s.tier = 'runtime',
                s.updatedAt = datetime()
            """,
            name=meta.name, description=meta.description,
        )
    for dependent, dependency in _REQUIRES_EDGES:
        neo4j.run(
            """
            MATCH (dependent:Skill {name: $dependent}), (dependency:Skill {name: $dependency})
            MERGE (dependent)-[:REQUIRES]->(dependency)
            """,
            dependent=dependent, dependency=dependency,
        )


def find_relevant_skills(
    neo4j: Neo4jClient, task_description: str, *, domain: str | None = None, limit: int = 5,
) -> list[SkillMatch]:
    """Full-text search over skill descriptions/names, boosted by domain
    relevance where present, ordered by relevance -- PLAN.md §2.9.14's
    "Skill Discovery Tool", minus the EntityType/Domain boosts this project
    has no real seeded data for yet (kept domain-agnostic rather than
    inventing fixture domains)."""
    rows = neo4j.run(
        """
        CALL db.index.fulltext.queryNodes('skill_description_index', $search_text) YIELD node AS s, score AS textScore
        WHERE s.confidence IS NULL OR s.confidence > 0.5
        OPTIONAL MATCH (s)-[:USED_IN]->(dom:Domain)
        WITH s, textScore, CASE WHEN $domain IS NULL THEN 0.0 WHEN dom.name = $domain THEN 0.2 ELSE 0.0 END AS domainBoost
        OPTIONAL MATCH (s)-[:REQUIRES]->(req:Skill)
        WITH s, textScore + domainBoost AS totalScore, collect(DISTINCT req.name) AS requires
        RETURN s.name AS name, s.description AS description, coalesce(s.confidence, 1.0) AS confidence,
               totalScore AS score, requires
        ORDER BY totalScore DESC
        LIMIT $limit
        """,
        search_text=_escape_lucene(task_description), domain=domain, limit=limit,
    )
    return [
        SkillMatch(name=r["name"], description=r["description"], confidence=r["confidence"], score=r["score"], requires=r["requires"])
        for r in rows
    ]


def record_skill_usage(
    neo4j: Neo4jClient, *, skill_name: str, session_id: str, success: bool,
    accuracy: float | None = None, tokens_used: int | None = None, error: str | None = None,
) -> float:
    """Appends an immutable :SkillUsage node (PLAN.md §2.9.14's usage
    tracking) and recomputes the skill's confidence as a rolling average of
    every recorded success/failure -- real learning signal, not a static
    hand-set number."""
    neo4j.run(
        """
        MERGE (s:Skill {name: $skill_name})
        ON CREATE SET s.description = '', s.tier = 'runtime', s.createdAt = datetime()
        CREATE (u:SkillUsage {
            id: $usage_id, skillName: $skill_name, sessionId: $session_id,
            loadedAt: datetime(), success: $success, accuracy: $accuracy,
            tokensUsed: $tokens_used, error: $error
        })
        MERGE (u)-[:USED_SKILL]->(s)
        """,
        skill_name=skill_name, session_id=session_id, usage_id=f"usage-{uuid.uuid4().hex[:12]}",
        success=success, accuracy=accuracy, tokens_used=tokens_used, error=error,
    )
    rows = neo4j.run(
        """
        MATCH (u:SkillUsage)-[:USED_SKILL]->(s:Skill {name: $skill_name})
        WITH s, avg(CASE WHEN u.success THEN 1.0 ELSE 0.0 END) AS newConfidence
        SET s.confidence = newConfidence, s.updatedAt = datetime()
        RETURN newConfidence
        """,
        skill_name=skill_name,
    )
    return rows[0]["newConfidence"]


def _escape_lucene(text: str) -> str:
    """Lucene special characters break db.index.fulltext.queryNodes if
    unescaped (e.g. a task description containing a colon or parenthesis) --
    quote the whole query as a single OR'd term list instead of a Lucene
    query-syntax string."""
    words = [w for w in text.replace("\n", " ").split(" ") if w.strip()]
    escaped = [w.translate(str.maketrans({c: f"\\{c}" for c in '+-&&||!(){}[]^"~*?:\\/'})) for w in words]
    return " OR ".join(escaped) if escaped else text
