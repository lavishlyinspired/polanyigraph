"""Tests for services/summary_service.py (PLAN.md §20 item 3). LLM is faked
(network-free); this proves the prompt is built from real inputs (existing
summary + new source text), not that the LLM itself is good."""

from __future__ import annotations

from services import summary_service


class FakeLLM:
    def __init__(self, response: str) -> None:
        self._response = response
        self.last_call: dict[str, str] | None = None

    def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        self.last_call = {"system": system, "user": user}
        return self._response


def test_generate_summary_returns_llm_output_stripped():
    llm = FakeLLM("  Acme Corp is a business entity domiciled in Zurich.  ")

    summary = summary_service.generate_summary(
        llm, label="Acme Corp", type_="organization", existing_summary="", new_context="Acme Corp is domiciled in Zurich."
    )

    assert summary == "Acme Corp is a business entity domiciled in Zurich."


def test_generate_summary_prompt_includes_existing_summary_and_new_context():
    llm = FakeLLM("updated summary")

    summary_service.generate_summary(
        llm, label="Acme Corp", type_="organization",
        existing_summary="Acme Corp is a Swiss company.",
        new_context="Acme Corp issued preferred stock in 2025.",
    )

    assert llm.last_call is not None
    combined = llm.last_call["system"] + llm.last_call["user"]
    assert "Acme Corp is a Swiss company." in combined
    assert "Acme Corp issued preferred stock in 2025." in combined
    assert "Acme Corp" in combined
    assert "organization" in combined


def test_generate_summary_with_no_existing_summary_still_works():
    llm = FakeLLM("first summary")

    summary = summary_service.generate_summary(
        llm, label="Acme Corp", type_="organization", existing_summary="", new_context="Acme Corp filed a report."
    )

    assert summary == "first summary"
    assert "none yet" in llm.last_call["user"].lower() or "none yet" in llm.last_call["system"].lower()
