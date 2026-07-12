"""Hybrid/resilient skill discovery (PLAN.md §18 / §2.9.14): combines the
fast filesystem catalog (agents/skill_store.py, always available) with the
Neo4j skill graph (services/skill_graph_service.py, relationship- and
usage-aware). ResilientSkillDiscovery adds the fallback PLAN.md §2.9.14 "When
Neo4j Is Unavailable" specifies -- graph queries degrade to filesystem
keyword matching rather than taking the agent down with them.
"""

from __future__ import annotations

from agents import skill_store
from db.neo4j_client import Neo4jClient
from services.skill_graph_service import SkillMatch, find_relevant_skills, record_skill_usage


class HybridSkillDiscovery:
    """Fast path (filesystem) for the always-needed catalog/content; rich
    path (Neo4j) for relationship- and confidence-aware discovery."""

    def __init__(self, neo4j: Neo4jClient) -> None:
        self._neo4j = neo4j

    def get_catalog(self) -> str:
        """In-memory catalog for a system prompt -- filesystem-only,
        works regardless of Neo4j's availability."""
        metas = skill_store.scan()
        return "\n".join(f"- {m.name}: {m.description}" for m in metas)

    def find_skills(self, task: str, *, domain: str | None = None, limit: int = 5) -> list[SkillMatch]:
        return find_relevant_skills(self._neo4j, task, domain=domain, limit=limit)

    def load_skill(self, name: str) -> str:
        return skill_store.load(name)

    def record_usage(
        self, name: str, *, session_id: str, success: bool,
        accuracy: float | None = None, tokens_used: int | None = None, error: str | None = None,
    ) -> float | None:
        return record_skill_usage(
            self._neo4j, skill_name=name, session_id=session_id, success=success,
            accuracy=accuracy, tokens_used=tokens_used, error=error,
        )


class ResilientSkillDiscovery(HybridSkillDiscovery):
    """Same interface as HybridSkillDiscovery, but find_skills/record_usage
    never propagate a Neo4j failure -- an agent turn should degrade (worse
    discovery, no usage history recorded) rather than crash because the
    graph database happened to be down."""

    def find_skills(self, task: str, *, domain: str | None = None, limit: int = 5) -> list[SkillMatch]:
        try:
            return super().find_skills(task, domain=domain, limit=limit)
        except Exception:
            return self._filesystem_fallback(task, limit=limit)

    def record_usage(
        self, name: str, *, session_id: str, success: bool,
        accuracy: float | None = None, tokens_used: int | None = None, error: str | None = None,
    ) -> float | None:
        try:
            return super().record_usage(name, session_id=session_id, success=success, accuracy=accuracy, tokens_used=tokens_used, error=error)
        except Exception:
            return None

    def _filesystem_fallback(self, task: str, *, limit: int) -> list[SkillMatch]:
        """Simple keyword overlap against the cached filesystem metadata --
        PLAN.md §2.9.14's fallback, not the graph's full-text ranking, but
        enough to keep the agent functional with Neo4j down."""
        task_words = {w for w in task.lower().split() if len(w) > 2}
        matches = []
        for meta in skill_store.scan():
            desc_words = {w.strip(".,()") for w in meta.description.lower().split()}
            overlap = len(task_words & desc_words)
            if overlap == 0:
                continue
            score = overlap / len(task_words)
            matches.append(SkillMatch(name=meta.name, description=meta.description, confidence=1.0, score=score, requires=[]))
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[:limit]
