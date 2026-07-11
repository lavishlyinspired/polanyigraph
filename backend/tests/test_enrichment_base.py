"""Tests for enrichment/heuristics/base.py -- shared machinery for the 11
Polanyi enrichment heuristics (PLAN.md §19). LLM is faked (network-free); this
proves parsing/validation, not that any LLM's causal reasoning is good."""

from __future__ import annotations

from enrichment.heuristics.base import (
    HEURISTIC_TYPES,
    build_base_graph_text,
    run_heuristic,
)
from services.graph_service import GraphEdgeRecord, GraphNodeRecord


class FakeLLM:
    def __init__(self, response: str) -> None:
        self._response = response
        self.last_call: dict[str, str] | None = None

    def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        self.last_call = {"system": system, "user": user}
        return self._response


def test_heuristic_types_has_exactly_the_11_polanyi_categories():
    assert HEURISTIC_TYPES == {
        "presupposition",
        "conversational_implicature",
        "factual_impact",
        "image_schema",
        "metonymic_coercion",
        "moral_value_coercion",
        "symbolic_coercion",
        "event_sequence",
        "causal_relation",
        "implied_future_event",
        "implied_non_event",
    }


def test_build_base_graph_text_renders_entities_and_relationships():
    nodes = [GraphNodeRecord(id="e1", label="Acme Corp", type="organization"), GraphNodeRecord(id="e2", label="Zurich", type="jurisdiction")]
    edges = [GraphEdgeRecord(id="r1", source="e1", target="e2", type="is domiciled in")]

    text = build_base_graph_text(nodes, edges)

    assert "Acme Corp" in text
    assert "Zurich" in text
    assert "is domiciled in" in text


def test_build_base_graph_text_handles_empty_graph():
    text = build_base_graph_text([], [])
    assert "no entities" in text.lower()
    assert "no relationships" in text.lower()


def test_run_heuristic_rejects_unknown_heuristic_type():
    llm = FakeLLM("{}")
    import pytest

    with pytest.raises(ValueError):
        run_heuristic(llm, heuristic_type="not_a_real_heuristic", system="s", user="u", valid_entity_ids={"e1"})


def test_run_heuristic_parses_valid_facts_anchored_to_real_entities():
    llm = FakeLLM('{"facts": [{"text": "The rain caused the delay.", "anchors": ["e1"], "confidence": 0.8}]}')

    result = run_heuristic(llm, heuristic_type="causal_relation", system="s", user="u", valid_entity_ids={"e1", "e2"})

    assert len(result.candidates) == 1
    assert result.candidates[0].text == "The rain caused the delay."
    assert result.candidates[0].heuristic_type == "causal_relation"
    assert result.candidates[0].anchor_entity_ids == ("e1",)
    assert result.candidates[0].confidence == 0.8
    assert result.dropped == []


def test_run_heuristic_drops_facts_with_no_valid_anchors():
    llm = FakeLLM('{"facts": [{"text": "Made up fact.", "anchors": ["does-not-exist"], "confidence": 0.9}]}')

    result = run_heuristic(llm, heuristic_type="causal_relation", system="s", user="u", valid_entity_ids={"e1"})

    assert result.candidates == []
    assert len(result.dropped) == 1
    assert "does-not-exist" in result.dropped[0]


def test_run_heuristic_drops_facts_missing_text():
    llm = FakeLLM('{"facts": [{"text": "", "anchors": ["e1"], "confidence": 0.5}]}')

    result = run_heuristic(llm, heuristic_type="causal_relation", system="s", user="u", valid_entity_ids={"e1"})

    assert result.candidates == []
    assert len(result.dropped) == 1


def test_run_heuristic_handles_unparseable_json():
    llm = FakeLLM("not json at all")

    result = run_heuristic(llm, heuristic_type="causal_relation", system="s", user="u", valid_entity_ids={"e1"})

    assert result.candidates == []
    assert "Could not parse" in result.dropped[0]


def test_run_heuristic_returns_empty_when_no_implicit_facts_found():
    llm = FakeLLM('{"facts": []}')

    result = run_heuristic(llm, heuristic_type="causal_relation", system="s", user="u", valid_entity_ids={"e1"})

    assert result.candidates == []
    assert result.dropped == []
