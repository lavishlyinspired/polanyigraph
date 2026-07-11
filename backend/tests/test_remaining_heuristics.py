"""Tests for the remaining 10 of the 11 Polanyi heuristics (PLAN.md §19.6 step 4)
-- mechanical repetition of the pattern proven by causal_relations.py, so one
parametrized test file covers the shared contract for all of them: each module
exposes HEURISTIC_TYPE (a real member of base.HEURISTIC_TYPES), builds a prompt
containing the source text and its own paper-sourced few-shot example, and drops
facts anchored to entities that don't exist in the graph."""

from __future__ import annotations

import pytest

from enrichment.heuristics import (
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
from enrichment.heuristics.base import HEURISTIC_TYPES
from services.graph_service import GraphNodeRecord

# (module, expected HEURISTIC_TYPE, a keyword from the paper's own worked
# example for that heuristic that must appear in the built prompt)
MODULES = [
    (presuppositions, "presupposition", "gold medal"),
    (conversational_implicatures, "conversational_implicature", "gas station"),
    (factual_impact, "factual_impact", "adrenaline"),
    (image_schemas, "image_schema", "container"),
    (metonymic_coercion, "metonymic_coercion", "white house"),
    (moral_value_coercion, "moral_value_coercion", "keeps her promises"),
    (symbolic_coercion, "symbolic_coercion", "symbolic"),
    (event_sequences, "event_sequence", "two days"),
    (implied_future_events, "implied_future_event", "committee"),
    (implied_non_events, "implied_non_event", "decided not to compete"),
]


class FakeLLM:
    def __init__(self, response: str) -> None:
        self._response = response
        self.last_call: dict[str, str] | None = None

    def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        self.last_call = {"system": system, "user": user}
        return self._response


@pytest.mark.parametrize("module,expected_type,example_keyword", MODULES)
def test_heuristic_type_is_a_real_polanyi_category(module, expected_type, example_keyword):
    assert module.HEURISTIC_TYPE == expected_type
    assert module.HEURISTIC_TYPE in HEURISTIC_TYPES


@pytest.mark.parametrize("module,expected_type,example_keyword", MODULES)
def test_prompt_includes_source_text_and_paper_sourced_example(module, expected_type, example_keyword):
    nodes = [GraphNodeRecord(id="e1", label="Acme Corp", type="organization")]
    llm = FakeLLM('{"facts": []}')

    module.run(llm, nodes=nodes, edges=[], source_text="Acme Corp filed a report.")

    assert llm.last_call is not None
    assert llm.last_call["user"] == "Acme Corp filed a report."
    assert example_keyword.lower() in llm.last_call["system"].lower()


@pytest.mark.parametrize("module,expected_type,example_keyword", MODULES)
def test_run_returns_correctly_typed_candidates_anchored_to_real_entities(module, expected_type, example_keyword):
    nodes = [GraphNodeRecord(id="e1", label="Acme Corp", type="organization")]
    llm = FakeLLM('{"facts": [{"text": "an implicit fact", "anchors": ["e1"], "confidence": 0.7}]}')

    result = module.run(llm, nodes=nodes, edges=[], source_text="text")

    assert len(result.candidates) == 1
    assert result.candidates[0].heuristic_type == expected_type
    assert result.candidates[0].anchor_entity_ids == ("e1",)


@pytest.mark.parametrize("module,expected_type,example_keyword", MODULES)
def test_run_drops_facts_anchored_to_entities_not_in_this_graph(module, expected_type, example_keyword):
    nodes = [GraphNodeRecord(id="e1", label="Acme Corp", type="organization")]
    llm = FakeLLM('{"facts": [{"text": "fabricated", "anchors": ["not-real"], "confidence": 0.5}]}')

    result = module.run(llm, nodes=nodes, edges=[], source_text="text")

    assert result.candidates == []
    assert len(result.dropped) == 1
