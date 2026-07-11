"""Metonymic Coercion heuristic (PLAN.md §19.1/§19.6 step 4).

Paper's definition (§3.2, Maudslay et al. 2024): "Metonymic coercion is a
linguistic phenomenon where a word's typical or literal sense is overridden
by a specific, related sense within its extended semantics... For example, in
the sentence 'The White House announced new policies', 'White House'
undergoes metonymic coercion to represent the U.S. government or
administration, rather than the physical building."
"""

from __future__ import annotations

from enrichment.heuristics.base import HeuristicLLM, HeuristicResult, build_base_graph_text, run_heuristic
from services.graph_service import GraphEdgeRecord, GraphNodeRecord

HEURISTIC_TYPE = "metonymic_coercion"

_SYSTEM_TEMPLATE = """You are an expert ontology engineer extending a knowledge graph with \
implicit knowledge. Task: identify Metonymic Coercion -- where a word's literal sense in \
the source text is overridden by a specific, related sense (part-for-whole or \
whole-for-part), not already captured as an explicit entity or edge in the graph below.

Example: in the sentence "The White House announced new policies", "White House" undergoes \
metonymic coercion to represent the U.S. government or administration, rather than the \
physical building.

Graph so far:
{base_graph}

Respond with ONLY a JSON object of this exact shape, no prose:
{{
  "facts": [
    {{"text": string, "anchors": [entity id, ...], "confidence": number 0-1}}
  ]
}}
Each "text" is one metonymic reinterpretation stated in natural language (name the \
literal term and what it actually refers to). Each "anchors" list must name the real \
entity id(s) from the graph above this coercion is about -- never invent an entity id \
that isn't listed. If no metonymic shift is implied, return an empty "facts" list."""


def run(
    llm: HeuristicLLM, *, nodes: list[GraphNodeRecord], edges: list[GraphEdgeRecord], source_text: str
) -> HeuristicResult:
    base_graph = build_base_graph_text(nodes, edges)
    system = _SYSTEM_TEMPLATE.format(base_graph=base_graph)
    valid_ids = {n.id for n in nodes}
    return run_heuristic(llm, heuristic_type=HEURISTIC_TYPE, system=system, user=source_text, valid_entity_ids=valid_ids)
