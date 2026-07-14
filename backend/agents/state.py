"""LangGraph agent state (MVP_PLAN.md Phase 6): extractor -> reasoner -> responder."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class AgentState(TypedDict):
    graph_id: str
    text: str
    # Set by the router node: "extract" | "enrich" | "query" | "reason" | "visualize"
    # | "recall" | "compound" (2026-07-13 plan §6, only when
    # settings.enable_compound_queries and the router lists >1 capability).
    intent: str
    # Set by the router node (2026-07-13 plan §6): the full parsed intent
    # list, len 1 in the common case (and always len 1 when
    # enable_compound_queries is False -- the LLM is never told compound is
    # an option, so this is provably identical to [intent] then).
    intents: list[str]
    entities_extracted: int
    relationships_extracted: int
    facts_derived: int
    fact_texts: list[str]
    enrichment_fact_texts: list[str]
    query_results: list[str]
    query_error: str
    # Set by the memory_agent node when intent == "recall".
    memory_hits: list[str]
    # Set by the analyst node when intent == "analyze" (PLAN: plans/
    # analytical-engine.md Slice 9): one "label: score" line per node,
    # highest score first -- same simplified-text-for-the-LLM convention as
    # query_results/fact_texts, not the raw AlgorithmResult object.
    analytics_summary: list[str]
    # Set by the router node (PLAN.md §18/§2.9.14, extended by 2026-07-13
    # plan §2 Stage A): real find_relevant_skills results for this turn's
    # text, most-relevant first. discovered_skill_scores is the parallel,
    # same-order relevance score for each name -- responder_node's
    # _select_skill uses discovered_skills[0]/discovered_skill_scores[0] to
    # decide whether discovery's top match should override _SKILL_BY_INTENT.
    discovered_skills: list[str]
    discovered_skill_scores: list[float]
    # 2026-07-13 plan §6: written additively by parallel specialist branches
    # when len(intents) > 1. Annotated[..., operator.or_] is required, not
    # decorative -- without it, two specialist nodes writing to this key in
    # the same parallel superstep raises LangGraph's InvalidUpdateError.
    # Verified against the installed langgraph version via a throwaway spike
    # before wiring this in (plan §6.9).
    partial_answers: Annotated[dict[str, dict], operator.or_]
    # Set by combiner_node (2026-07-13 plan §6), deterministic synthesis of
    # partial_answers -- read by responder_node's "compound" branch.
    combined_answer: str
    reply: str
