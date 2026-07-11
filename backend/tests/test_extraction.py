"""Extraction pipeline tests. LLM is injected (a fake) so these run without
network — per the kg-extraction skill's definition of done. Validation is
against a real OntologySchema shape (built from real FIBO labels confirmed
against the live repo), not a fixture ontology.
"""

from __future__ import annotations

import json

from extraction.pipeline import build_prompt, extract
from ontology.schema import OntologyClass, OntologyProperty, OntologySchema


class FakeLLM:
    def __init__(self, response: str) -> None:
        self._response = response
        self.last_call: dict[str, str] | None = None

    def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        self.last_call = {"system": system, "user": user}
        return self._response


def _schema() -> OntologySchema:
    # Real FIBO labels (confirmed live against the fibo repository).
    return OntologySchema(
        repository="fibo",
        classes=[
            OntologyClass(uri="urn:organization", label="organization"),
            OntologyClass(uri="urn:security", label="security"),
            OntologyClass(uri="urn:jurisdiction", label="jurisdiction"),
        ],
        properties=[
            OntologyProperty(uri="urn:issues", label="issues"),
            OntologyProperty(uri="urn:domiciled", label="is domiciled in"),
        ],
    )


def test_extract_validates_entities_against_ontology():
    payload = json.dumps({
        "entities": [
            {"name": "Acme Corp", "type": "organization", "confidence": 0.9},
            {"name": "Acme Preferred Stock", "type": "security", "confidence": 0.85},
        ],
        "relationships": [
            {"source": "Acme Corp", "relation": "issues", "target": "Acme Preferred Stock", "confidence": 0.8},
        ],
    })
    llm = FakeLLM(payload)

    result = extract("Acme Corp issued preferred stock.", schema=_schema(), llm=llm)

    assert {e.name for e in result.entities} == {"Acme Corp", "Acme Preferred Stock"}
    assert all(e.type in {"organization", "security"} for e in result.entities)
    assert len(result.relationships) == 1
    assert result.dropped == []


def test_extract_drops_entities_with_unknown_type():
    payload = json.dumps({
        "entities": [
            {"name": "Acme Corp", "type": "organization", "confidence": 0.9},
            {"name": "Random Thing", "type": "not-a-real-fibo-class", "confidence": 0.5},
        ],
        "relationships": [],
    })
    llm = FakeLLM(payload)

    result = extract("text", schema=_schema(), llm=llm)

    names = {e.name for e in result.entities}
    assert names == {"Acme Corp"}
    assert any("Random Thing" in d for d in result.dropped)


def test_extract_drops_relationships_with_unknown_relation():
    payload = json.dumps({
        "entities": [
            {"name": "Acme Corp", "type": "organization", "confidence": 0.9},
            {"name": "Acme Preferred Stock", "type": "security", "confidence": 0.9},
        ],
        "relationships": [
            {"source": "Acme Corp", "relation": "made-up-relation", "target": "Acme Preferred Stock", "confidence": 0.5},
        ],
    })
    llm = FakeLLM(payload)

    result = extract("text", schema=_schema(), llm=llm)
    assert result.relationships == []
    assert any("made-up-relation" in d for d in result.dropped)


def test_extract_is_case_insensitive_on_type_match():
    payload = json.dumps({
        "entities": [{"name": "Acme Corp", "type": "Organization", "confidence": 0.9}],
        "relationships": [],
    })
    llm = FakeLLM(payload)
    result = extract("text", schema=_schema(), llm=llm)
    assert len(result.entities) == 1


def test_extract_handles_malformed_json_gracefully():
    llm = FakeLLM("not json at all")
    result = extract("text", schema=_schema(), llm=llm)
    assert result.entities == []
    assert result.relationships == []
    assert any("parse" in d.lower() or "json" in d.lower() for d in result.dropped)


def test_prompt_includes_real_ontology_vocabulary():
    llm = FakeLLM(json.dumps({"entities": [], "relationships": []}))
    extract("some text", schema=_schema(), llm=llm)
    assert llm.last_call is not None
    assert "organization" in llm.last_call["system"] or "organization" in llm.last_call["user"]


def test_extra_guidance_is_appended_to_prompt_when_given():
    """PLAN.md §13.2: the agent's extractor node loads the kg-extraction
    runtime skill and passes its content through as extra_guidance."""
    system, _ = build_prompt("some text", _schema(), extra_guidance="Prefer precision over recall.")
    assert "Prefer precision over recall." in system


def test_extra_guidance_is_optional_and_prompt_unchanged_without_it():
    with_guidance, _ = build_prompt("some text", _schema(), extra_guidance="Extra rule.")
    without_guidance, _ = build_prompt("some text", _schema())
    assert without_guidance != with_guidance
    assert "Extra rule." not in without_guidance
