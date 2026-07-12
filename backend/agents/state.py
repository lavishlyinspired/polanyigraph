"""LangGraph agent state (MVP_PLAN.md Phase 6): extractor -> reasoner -> responder."""

from __future__ import annotations

from typing import TypedDict


class AgentState(TypedDict):
    graph_id: str
    text: str
    # Set by the router node: "extract" | "enrich" | "query" | "reason" | "visualize".
    intent: str
    entities_extracted: int
    relationships_extracted: int
    facts_derived: int
    fact_texts: list[str]
    enrichment_fact_texts: list[str]
    query_results: list[str]
    query_error: str
    # Set by the memory_agent node when intent == "recall".
    memory_hits: list[str]
    # Set by the router node (PLAN.md §18/§2.9.14): real find_relevant_skills
    # results for this turn's text, most-relevant first -- observability into
    # what the skill graph actually recommended, independent of which skill
    # _SKILL_BY_INTENT deterministically loads.
    discovered_skills: list[str]
    reply: str
