"""Tests for enrichment/heuristics/causal_relations.py -- the first of the 11
Polanyi heuristics implemented (PLAN.md §19.6), proving the pattern in
base.py before the remaining 10 are mechanical repetition."""

from __future__ import annotations

from enrichment.heuristics import causal_relations
from services.graph_service import GraphEdgeRecord, GraphNodeRecord


class FakeLLM:
    def __init__(self, response: str) -> None:
        self._response = response
        self.last_call: dict[str, str] | None = None

    def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        self.last_call = {"system": system, "user": user}
        return self._response


def test_run_builds_prompt_from_real_graph_and_source_text():
    nodes = [GraphNodeRecord(id="e1", label="the match", type="event")]
    edges: list[GraphEdgeRecord] = []
    llm = FakeLLM('{"facts": []}')

    causal_relations.run(llm, nodes=nodes, edges=edges, source_text="The heavy rain forced the match to be postponed.")

    assert llm.last_call is not None
    assert "the match" in llm.last_call["system"]
    assert llm.last_call["user"] == "The heavy rain forced the match to be postponed."
    # The paper's own worked example (§3.2) should ground the few-shot prompt.
    assert "heavy rain" in llm.last_call["system"].lower()


def test_run_returns_causal_relation_typed_candidates():
    nodes = [GraphNodeRecord(id="e1", label="the match", type="event")]
    llm = FakeLLM('{"facts": [{"text": "The heavy rain caused the match to be postponed.", "anchors": ["e1"], "confidence": 0.9}]}')

    result = causal_relations.run(llm, nodes=nodes, edges=[], source_text="The heavy rain forced the match to be postponed.")

    assert len(result.candidates) == 1
    assert result.candidates[0].heuristic_type == "causal_relation"
    assert result.candidates[0].anchor_entity_ids == ("e1",)


def test_run_drops_facts_anchored_to_entities_not_in_this_graph():
    nodes = [GraphNodeRecord(id="e1", label="the match", type="event")]
    llm = FakeLLM('{"facts": [{"text": "fabricated", "anchors": ["not-real"], "confidence": 0.5}]}')

    result = causal_relations.run(llm, nodes=nodes, edges=[], source_text="text")

    assert result.candidates == []
    assert len(result.dropped) == 1
