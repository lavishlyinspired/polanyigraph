"""Implied Future Events heuristic (PLAN.md §19.1/§19.6 step 4).

Paper's definition (§3.2, Motta et al. 2024): "Implied future events involve
inferring likely outcomes or consequences based on given information... For
example, in the sentence 'The committee announced more strict regulations',
the system might infer potential future events such as more severe checks,
increase in bureaucratic practices, increase in controversy, etc."
"""

from __future__ import annotations

from enrichment.heuristics.base import HeuristicLLM, HeuristicResult, build_base_graph_text, run_heuristic
from services.graph_service import GraphEdgeRecord, GraphNodeRecord

HEURISTIC_TYPE = "implied_future_event"

_SYSTEM_TEMPLATE = """You are an expert ontology engineer extending a knowledge graph with \
implicit knowledge. Task: identify Implied Future Events -- likely outcomes or consequences \
implied by the source text that have not yet happened and are not already stated as \
explicit entities or edges in the graph below.

Example: in the sentence "The committee announced more strict regulations", plausible \
implied future events include more severe checks, increased bureaucratic practices, and \
increased controversy.

Graph so far:
{base_graph}

Respond with ONLY a JSON object of this exact shape, no prose:
{{
  "facts": [
    {{"text": string, "anchors": [entity id, ...], "confidence": number 0-1}}
  ]
}}
Each "text" is one plausible future event stated in natural language. Each "anchors" list \
must name the real entity id(s) from the graph above this prediction is about -- never \
invent an entity id that isn't listed. If no future event is plausibly implied, return an \
empty "facts" list."""


def run(
    llm: HeuristicLLM, *, nodes: list[GraphNodeRecord], edges: list[GraphEdgeRecord], source_text: str
) -> HeuristicResult:
    base_graph = build_base_graph_text(nodes, edges)
    system = _SYSTEM_TEMPLATE.format(base_graph=base_graph)
    valid_ids = {n.id for n in nodes}
    return run_heuristic(llm, heuristic_type=HEURISTIC_TYPE, system=system, user=source_text, valid_entity_ids=valid_ids)
