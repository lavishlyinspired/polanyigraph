"""Real-LLM extraction: text -> entities/relationships, validated against the
live ontology schema (see kg-extraction SKILL.md). Domain-agnostic: the prompt
vocabulary and the validation both come from the injected `OntologySchema`,
never a hardcoded type list.

An ontology like FIBO has thousands of classes — too many for one prompt — so
the prompt is built from a relevance-ranked subset (simple token overlap
against the input text), and validation double-checks whatever the model
returns against the *full* schema, not just the subset offered. Anything that
doesn't match a real ontology class/property is dropped, not guessed through.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from llm.client import LLMClient
from ontology.schema import OntologySchema

_MAX_PROMPT_CLASSES = 60
_MAX_PROMPT_PROPERTIES = 40

_SYSTEM_TEMPLATE = """You are an information extraction engine. Extract entities and \
relationships from the user's text using ONLY the following ontology vocabulary.

Entity types (use the exact label):
{classes}

Relationship types (use the exact label):
{properties}

Respond with ONLY a JSON object of this exact shape, no prose:
{{
  "entities": [{{"name": string, "type": string, "confidence": number 0-1}}],
  "relationships": [{{"source": string, "relation": string, "target": string, "confidence": number 0-1}}]
}}
Only use entity types and relationship types from the vocabulary above. If nothing \
in the text matches the vocabulary, return empty lists."""


@dataclass(frozen=True)
class ExtractedEntity:
    name: str
    type: str
    confidence: float = 1.0


@dataclass(frozen=True)
class ExtractedRelationship:
    source: str
    relation: str
    target: str
    confidence: float = 1.0


@dataclass(frozen=True)
class ExtractionResult:
    entities: list[ExtractedEntity] = field(default_factory=list)
    relationships: list[ExtractedRelationship] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _rank_by_overlap(labels: list[str], text_tokens: set[str], limit: int) -> list[str]:
    def score(label: str) -> int:
        return len(_tokenize(label) & text_tokens)

    ranked = sorted(labels, key=score, reverse=True)
    # Keep the ranking real-data-driven but always include a floor of labels
    # even with zero overlap, so short/terse input text still gets a usable
    # vocabulary to extract against.
    return ranked[:limit]


def build_prompt(text: str, schema: OntologySchema, extra_guidance: str = "") -> tuple[str, str]:
    tokens = _tokenize(text)
    classes = _rank_by_overlap(schema.class_labels, tokens, _MAX_PROMPT_CLASSES)
    properties = _rank_by_overlap(schema.property_labels, tokens, _MAX_PROMPT_PROPERTIES)
    system = _SYSTEM_TEMPLATE.format(classes="\n".join(f"- {c}" for c in classes), properties="\n".join(f"- {p}" for p in properties))
    # PLAN.md §13.2: the agent's extractor node loads the kg-extraction
    # runtime skill (backend/skills/) and passes its content through here --
    # optional so extraction/ingest_service.py's direct callers are unaffected.
    if extra_guidance:
        system = f"{system}\n\n{extra_guidance}"
    return system, text


def extract(text: str, *, schema: OntologySchema, llm: LLMClient, extra_guidance: str = "") -> ExtractionResult:
    system, user = build_prompt(text, schema, extra_guidance)
    raw = llm.complete_json(system=system, user=user)

    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return ExtractionResult(dropped=[f"Could not parse LLM response as JSON: {raw[:120]!r}"])

    dropped: list[str] = []
    entities: list[ExtractedEntity] = []
    known_names: set[str] = set()

    for raw_entity in payload.get("entities", []):
        name = str(raw_entity.get("name", "")).strip()
        type_ = str(raw_entity.get("type", "")).strip()
        if not name or not type_:
            dropped.append(f"Entity missing name/type: {raw_entity}")
            continue
        if not schema.is_known_type(type_):
            dropped.append(f"Entity '{name}' has unknown ontology type '{type_}'")
            continue
        entities.append(ExtractedEntity(name=name, type=type_, confidence=float(raw_entity.get("confidence", 1.0))))
        known_names.add(name.lower())

    known_properties = {p.lower() for p in schema.property_labels}
    relationships: list[ExtractedRelationship] = []
    for raw_rel in payload.get("relationships", []):
        source = str(raw_rel.get("source", "")).strip()
        relation = str(raw_rel.get("relation", "")).strip()
        target = str(raw_rel.get("target", "")).strip()
        if relation.lower() not in known_properties:
            dropped.append(f"Relationship has unknown relation type '{relation}'")
            continue
        if source.lower() not in known_names or target.lower() not in known_names:
            dropped.append(f"Relationship '{source} {relation} {target}' references an unextracted entity")
            continue
        relationships.append(
            ExtractedRelationship(source=source, relation=relation, target=target, confidence=float(raw_rel.get("confidence", 1.0)))
        )

    return ExtractionResult(entities=entities, relationships=relationships, dropped=dropped)
