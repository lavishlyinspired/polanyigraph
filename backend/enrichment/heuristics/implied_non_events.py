"""Implied (Potential) Non-Events heuristic (PLAN.md §19.1/§19.6 step 4).

Paper's definition (§3.2, Motta et al. 2024): "Implied potential non-events
are events that could have occurred but are prevented or made unlikely due to
other circumstances or decisions mentioned in the text... For example, in the
sentence 'She decided not to compete', the system would recognize the implied
potential non-event of participating in the competition, allowing for
analysis of the decision's consequences and alternative outcomes."
"""

from __future__ import annotations

from enrichment.heuristics.base import HeuristicLLM, HeuristicResult, build_base_graph_text, run_heuristic
from services.graph_service import GraphEdgeRecord, GraphNodeRecord

HEURISTIC_TYPE = "implied_non_event"

_SYSTEM_TEMPLATE = """You are an expert ontology engineer extending a knowledge graph with \
implicit knowledge. Task: identify Implied Potential Non-Events -- counterfactual \
alternatives the source text implies were foreclosed by a decision or circumstance, not \
already captured as an explicit entity or edge in the graph below.

Example: in the sentence "She decided not to compete", the implied potential non-event is \
her participating in the competition -- an alternative outcome her decision foreclosed.

Graph so far:
{base_graph}

Respond with ONLY a JSON object of this exact shape, no prose:
{{
  "facts": [
    {{"text": string, "anchors": [entity id, ...], "confidence": number 0-1}}
  ]
}}
Each "text" is one foreclosed counterfactual alternative stated in natural language. Each \
"anchors" list must name the real entity id(s) from the graph above this alternative is \
about -- never invent an entity id that isn't listed. The example above ("She decided not \
to compete") is illustrative only -- do not repeat it or any part of it in your output \
unless it verbatim appears in the source text below. If no potential non-event is implied \
by the source text itself, return an empty "facts" list."""


def run(
    llm: HeuristicLLM, *, nodes: list[GraphNodeRecord], edges: list[GraphEdgeRecord], source_text: str
) -> HeuristicResult:
    base_graph = build_base_graph_text(nodes, edges)
    system = _SYSTEM_TEMPLATE.format(base_graph=base_graph)
    valid_ids = {n.id for n in nodes}
    return run_heuristic(llm, heuristic_type=HEURISTIC_TYPE, system=system, user=source_text, valid_entity_ids=valid_ids)
