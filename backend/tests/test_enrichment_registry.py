"""Tests for the heuristic registry + run_all_heuristics dispatcher (PLAN.md
§19.2: all 11 heuristics ship together, not filtered by domain -- so a single
enrichment pass runs every one of them, not just Causal Relations)."""

from __future__ import annotations

from enrichment.heuristics import ALL_HEURISTIC_MODULES
from enrichment.heuristics.base import HEURISTIC_TYPES
from services import enrichment_service
from services.graph_service import GraphNodeRecord


class FakeLLM:
    """Returns a fact anchored to the real entity for every heuristic prompt --
    proves the dispatcher actually invokes all 11, not just one."""

    def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        return '{"facts": [{"text": "an implicit fact", "anchors": ["e1"], "confidence": 0.6}]}'


def test_all_heuristic_modules_registry_has_exactly_11_entries_matching_the_typology():
    assert len(ALL_HEURISTIC_MODULES) == 11
    assert {m.HEURISTIC_TYPE for m in ALL_HEURISTIC_MODULES} == HEURISTIC_TYPES


def test_run_all_heuristics_produces_one_candidate_set_per_heuristic():
    nodes = [GraphNodeRecord(id="e1", label="Acme Corp", type="organization")]
    llm = FakeLLM()

    candidates = enrichment_service.run_all_heuristics(llm, nodes=nodes, edges=[], source_text="Acme Corp filed a report.")

    assert len(candidates) == 11
    assert {c.heuristic_type for c in candidates} == HEURISTIC_TYPES
    assert all(c.anchor_entity_ids == ("e1",) for c in candidates)
