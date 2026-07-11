"""Conversational Implicatures heuristic (PLAN.md §19.1/§19.6 step 4).

Paper's definition (§3.2, Grice 1975): "Conversational implicatures are implied
meanings that arise from the context of a conversation rather than literal
interpretation... For example, if someone asks 'Is there a gas station
nearby?' and receives the answer 'There's one around the corner', the
implicature here is that the gas station should be open and operational, even
though this is not explicitly stated."
"""

from __future__ import annotations

from enrichment.heuristics.base import HeuristicLLM, HeuristicResult, build_base_graph_text, run_heuristic
from services.graph_service import GraphEdgeRecord, GraphNodeRecord

HEURISTIC_TYPE = "conversational_implicature"

_SYSTEM_TEMPLATE = """You are an expert ontology engineer extending a knowledge graph with \
implicit knowledge. Task: identify Conversational Implicatures (Gricean pragmatics) -- \
meaning that arises from the context of the source text rather than its literal content, \
that is NOT already an explicit entity or edge in the graph below.

Example: if someone asks "Is there a gas station nearby?" and receives the answer \
"There's one around the corner", the implicature is that the gas station should be open \
and operational -- even though that is not stated explicitly.

Graph so far:
{base_graph}

Respond with ONLY a JSON object of this exact shape, no prose:
{{
  "facts": [
    {{"text": string, "anchors": [entity id, ...], "confidence": number 0-1}}
  ]
}}
Each "text" is one implied meaning stated in natural language. Each "anchors" list must \
name the real entity id(s) from the graph above that this implicature is about -- never \
invent an entity id that isn't listed. If the text carries no implicature beyond its \
literal content, return an empty "facts" list."""


def run(
    llm: HeuristicLLM, *, nodes: list[GraphNodeRecord], edges: list[GraphEdgeRecord], source_text: str
) -> HeuristicResult:
    base_graph = build_base_graph_text(nodes, edges)
    system = _SYSTEM_TEMPLATE.format(base_graph=base_graph)
    valid_ids = {n.id for n in nodes}
    return run_heuristic(llm, heuristic_type=HEURISTIC_TYPE, system=system, user=source_text, valid_entity_ids=valid_ids)
