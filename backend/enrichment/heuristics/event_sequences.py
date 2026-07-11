"""Event Sequences heuristic (PLAN.md §19.1/§19.6 step 4).

Paper's definition (§3.2, Motta et al. 2024): "Event sequences capture the
chronological relationship between events mentioned in a text... For example,
in the sentence 'After the flight, the athletes have two days before the
competition', the system would recognize the sequence: flight -> two_days ->
competition, allowing for deeper comprehension of the narrative's timeline."
"""

from __future__ import annotations

from enrichment.heuristics.base import HeuristicLLM, HeuristicResult, build_base_graph_text, run_heuristic
from services.graph_service import GraphEdgeRecord, GraphNodeRecord

HEURISTIC_TYPE = "event_sequence"

_SYSTEM_TEMPLATE = """You are an expert ontology engineer extending a knowledge graph with \
implicit knowledge. Task: identify Event Sequences -- the implicit chronological ordering \
of events mentioned in the source text, not already captured as an explicit entity or edge \
in the graph below.

Example: in the sentence "After the flight, the athletes have two days before the \
competition", the implicit sequence is: flight -> two days -> competition.

Graph so far:
{base_graph}

Respond with ONLY a JSON object of this exact shape, no prose:
{{
  "facts": [
    {{"text": string, "anchors": [entity id, ...], "confidence": number 0-1}}
  ]
}}
Each "text" is one implicit chronological ordering stated in natural language (e.g. \
"X happens before Y"). Each "anchors" list must name the real entity id(s) from the graph \
above this ordering is about -- never invent an entity id that isn't listed. The example \
above (flight -> two days -> competition) is illustrative only -- do not repeat it or any \
part of it in your output unless it verbatim appears in the source text below. If no \
implicit sequence is present in the source text itself, return an empty "facts" list."""


def run(
    llm: HeuristicLLM, *, nodes: list[GraphNodeRecord], edges: list[GraphEdgeRecord], source_text: str
) -> HeuristicResult:
    base_graph = build_base_graph_text(nodes, edges)
    system = _SYSTEM_TEMPLATE.format(base_graph=base_graph)
    valid_ids = {n.id for n in nodes}
    return run_heuristic(llm, heuristic_type=HEURISTIC_TYPE, system=system, user=source_text, valid_entity_ids=valid_ids)
