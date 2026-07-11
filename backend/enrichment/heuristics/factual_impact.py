"""Factual Impact heuristic (PLAN.md §19.1/§19.6 step 4).

Paper's definition (§3.2, Kahneman 1991): "Factual impact refers to the
physical, social, and cognitive consequences of events on participants,
including expected emotions, sensations, and changes in mental states...
For example, in the event of 'winning a competition', the factual impact
might include physical sensations (adrenaline rush), emotions (joy, pride),
and cognitive changes (increased confidence, future goal-setting)."
"""

from __future__ import annotations

from enrichment.heuristics.base import HeuristicLLM, HeuristicResult, build_base_graph_text, run_heuristic
from services.graph_service import GraphEdgeRecord, GraphNodeRecord

HEURISTIC_TYPE = "factual_impact"

_SYSTEM_TEMPLATE = """You are an expert ontology engineer extending a knowledge graph with \
implicit knowledge. Task: identify Factual Impact -- the physical, social, and cognitive \
consequences of events on participants (expected emotions, sensations, changes in mental \
state) mentioned in the source text, that are NOT already explicit in the graph below.

Example: in the event of "winning a competition", the factual impact might include \
physical sensations (adrenaline rush), emotions (joy, pride), and cognitive changes \
(increased confidence, future goal-setting).

Graph so far:
{base_graph}

Respond with ONLY a JSON object of this exact shape, no prose:
{{
  "facts": [
    {{"text": string, "anchors": [entity id, ...], "confidence": number 0-1}}
  ]
}}
Each "text" is one implicit physical/social/cognitive consequence stated in natural \
language. Each "anchors" list must name the real entity id(s) from the graph above that \
this impact is about -- never invent an entity id that isn't listed. If no such impact is \
implied, return an empty "facts" list."""


def run(
    llm: HeuristicLLM, *, nodes: list[GraphNodeRecord], edges: list[GraphEdgeRecord], source_text: str
) -> HeuristicResult:
    base_graph = build_base_graph_text(nodes, edges)
    system = _SYSTEM_TEMPLATE.format(base_graph=base_graph)
    valid_ids = {n.id for n in nodes}
    return run_heuristic(llm, heuristic_type=HEURISTIC_TYPE, system=system, user=source_text, valid_entity_ids=valid_ids)
