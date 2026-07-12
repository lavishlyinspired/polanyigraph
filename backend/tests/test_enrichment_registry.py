"""Tests for the heuristic registry + run_all_heuristics dispatcher (PLAN.md
§19.2: all 11 heuristics ship together, not filtered by domain -- so a single
enrichment pass runs every one of them, not just Causal Relations)."""

from __future__ import annotations

import time

from enrichment.heuristics import ALL_HEURISTIC_MODULES
from enrichment.heuristics.base import HEURISTIC_TYPES
from services import enrichment_service
from services.graph_service import GraphNodeRecord


class FakeLLM:
    """Returns a fact anchored to the real entity for every heuristic prompt --
    proves the dispatcher actually invokes all 11, not just one."""

    def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        return '{"facts": [{"text": "an implicit fact", "anchors": ["e1"], "confidence": 0.6}]}'


class SlowFakeLLM:
    """Each call blocks for a fixed duration -- proves the 11 heuristic calls
    run concurrently (total wall time ~= one call, not 11x)."""

    def __init__(self, *, delay: float) -> None:
        self._delay = delay

    def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        time.sleep(self._delay)
        return '{"facts": [{"text": "an implicit fact", "anchors": ["e1"], "confidence": 0.6}]}'


class FlakyFakeLLM:
    """Raises for one specific heuristic's prompt (identified by a marker in
    the system prompt), succeeds for the rest -- proves one heuristic's
    failure doesn't sink the whole batch."""

    def __init__(self, *, fail_marker: str) -> None:
        self._fail_marker = fail_marker

    def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        if self._fail_marker in system:
            raise RuntimeError("simulated LLM failure")
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


def test_run_all_heuristics_runs_the_11_llm_calls_concurrently_not_sequentially():
    nodes = [GraphNodeRecord(id="e1", label="Acme Corp", type="organization")]
    llm = SlowFakeLLM(delay=0.2)

    started = time.perf_counter()
    candidates = enrichment_service.run_all_heuristics(llm, nodes=nodes, edges=[], source_text="Acme Corp filed a report.")
    elapsed = time.perf_counter() - started

    assert len(candidates) == 11
    # Sequential would take 11 * 0.2s = 2.2s; concurrent should be close to
    # one delay plus overhead. Generous margin to avoid CI flakiness.
    assert elapsed < 1.0, f"expected concurrent execution, took {elapsed:.2f}s"


def test_run_all_heuristics_isolates_a_single_heuristic_failure():
    nodes = [GraphNodeRecord(id="e1", label="Acme Corp", type="organization")]
    llm = FlakyFakeLLM(fail_marker="Causal Relations")

    candidates = enrichment_service.run_all_heuristics(llm, nodes=nodes, edges=[], source_text="Acme Corp filed a report.")

    assert len(candidates) == 10
    assert "causal_relation" not in {c.heuristic_type for c in candidates}
