"""Registry of all 11 Polanyi enrichment heuristics (PLAN.md §19.2: they ship
together, not filtered by domain -- so orchestration code iterates this list
rather than hardcoding one heuristic)."""

from __future__ import annotations

from enrichment.heuristics import (
    causal_relations,
    conversational_implicatures,
    event_sequences,
    factual_impact,
    image_schemas,
    implied_future_events,
    implied_non_events,
    metonymic_coercion,
    moral_value_coercion,
    presuppositions,
    symbolic_coercion,
)

ALL_HEURISTIC_MODULES = (
    presuppositions,
    conversational_implicatures,
    factual_impact,
    image_schemas,
    metonymic_coercion,
    moral_value_coercion,
    symbolic_coercion,
    event_sequences,
    causal_relations,
    implied_future_events,
    implied_non_events,
)
