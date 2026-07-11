"""Shared machinery for the 11 Polanyi enrichment heuristics (PLAN.md §19).

Each heuristic module builds a role + input-format + heuristic-definition +
few-shot-examples + output-format prompt (matching the paper's own §3.3.2
structure) against this project's already-extracted, ontology-typed graph
(the Base Graph, per §19.3 -- not an AMR/OWL graph) and calls run_heuristic(),
which parses the LLM's JSON response into ImplicitFactCandidate objects,
dropping anything that doesn't anchor to a real node -- the same
anchoring-integrity discipline extraction/pipeline.py applies to the ontology.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol

from services.graph_service import GraphEdgeRecord, GraphNodeRecord

# Polanyi's own fixed typology (§3.2 of the paper) -- not the swappable domain
# ontology. Every :ImplicitFact.heuristicType must be one of these.
HEURISTIC_TYPES = frozenset({
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
})


class HeuristicLLM(Protocol):
    def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str: ...


@dataclass(frozen=True)
class ImplicitFactCandidate:
    heuristic_type: str
    text: str
    confidence: float
    anchor_entity_ids: tuple[str, ...]


@dataclass(frozen=True)
class HeuristicResult:
    candidates: list[ImplicitFactCandidate] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)


def build_base_graph_text(nodes: list[GraphNodeRecord], edges: list[GraphEdgeRecord]) -> str:
    """Compact textual form of the Base Graph subset for a heuristic prompt."""
    entity_lines = "\n".join(f"- {n.label} (id: {n.id}, type: {n.type})" for n in nodes) or "(no entities)"
    label_by_id = {n.id: n.label for n in nodes}
    edge_lines = "\n".join(
        f"- {label_by_id.get(e.source, e.source)} --{e.type}--> {label_by_id.get(e.target, e.target)}"
        for e in edges
    ) or "(no relationships)"
    return f"Entities:\n{entity_lines}\n\nRelationships:\n{edge_lines}"


def run_heuristic(
    llm: HeuristicLLM, *, heuristic_type: str, system: str, user: str, valid_entity_ids: set[str]
) -> HeuristicResult:
    if heuristic_type not in HEURISTIC_TYPES:
        raise ValueError(f"Unknown heuristic type '{heuristic_type}' -- not one of Polanyi's 11 categories.")

    raw = llm.complete_json(system=system, user=user)
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return HeuristicResult(dropped=[f"Could not parse LLM response as JSON: {raw[:120]!r}"])

    candidates: list[ImplicitFactCandidate] = []
    dropped: list[str] = []
    for raw_fact in payload.get("facts", []):
        text = str(raw_fact.get("text", "")).strip()
        anchors = [str(a).strip() for a in raw_fact.get("anchors", [])]
        confidence = float(raw_fact.get("confidence", 0.5))
        if not text:
            dropped.append(f"Fact missing text: {raw_fact}")
            continue
        valid_anchors = [a for a in anchors if a in valid_entity_ids]
        if not valid_anchors:
            dropped.append(f"Fact '{text}' has no anchors referencing real entities in this graph: {anchors}")
            continue
        candidates.append(
            ImplicitFactCandidate(
                heuristic_type=heuristic_type, text=text, confidence=confidence,
                anchor_entity_ids=tuple(valid_anchors),
            )
        )
    return HeuristicResult(candidates=candidates, dropped=dropped)
