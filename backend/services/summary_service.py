"""Evolving entity summaries (PLAN.md §20 item 3, mirrors Graphiti's EntityNode.summary).

Each time an ingest references an entity again, this synthesizes the existing
summary with the newly ingested source text into one updated summary via a
real LLM call -- accumulating context across documents instead of the entity
staying pinned to whatever its first extraction happened to say.
"""

from __future__ import annotations

from typing import Protocol


class SummaryLLM(Protocol):
    def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str: ...


_SYSTEM = """You maintain a short, factual summary of a knowledge-graph entity as new \
source documents mention it. Synthesize the existing summary with the new source text \
into a single updated summary, 1-2 sentences, no speculation, no invented facts."""

_USER_TEMPLATE = """Entity: {label} ({type_})
Existing summary: {existing_summary}
New source text mentioning this entity:
{new_context}

Write one updated summary sentence or two."""


def generate_summary(
    llm: SummaryLLM, *, label: str, type_: str, existing_summary: str, new_context: str
) -> str:
    user = _USER_TEMPLATE.format(
        label=label, type_=type_,
        existing_summary=existing_summary or "(none yet)",
        new_context=new_context,
    )
    reply = llm.complete_json(system=_SYSTEM, user=user)
    return reply.strip()
