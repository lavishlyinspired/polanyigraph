"""Causal Relations heuristic (PLAN.md §19.1/§19.6) -- the first of the 11
Polanyi heuristics implemented, proving the pattern in base.py before the
remaining 10 (mechanical repetition once one is real and tested).

Paper's own definition (§3.2): "Causal relations capture the cause-and-effect
relationships between events or states mentioned in a text... enables the
system to infer and reason about underlying causes and effects within complex
scenarios, even when not explicitly stated." Worked example from the paper:
"The heavy rain forced the match to be postponed" implies the causal chain
heavy_rain -> match_postponing, even though the graph wouldn't have an
explicit "caused" edge for it.
"""

from __future__ import annotations

from enrichment.heuristics.base import HeuristicLLM, HeuristicResult, build_base_graph_text, run_heuristic
from services.graph_service import GraphEdgeRecord, GraphNodeRecord

HEURISTIC_TYPE = "causal_relation"

_SYSTEM_TEMPLATE = """You are an expert ontology engineer extending a knowledge graph with \
implicit knowledge. Task: identify Causal Relations -- cause-and-effect relationships \
between events or states mentioned in the source text that are NOT already explicit \
edges in the graph below. Causal relations let a reader infer and reason about \
underlying causes and effects, even when not explicitly stated.

Example: in the sentence "The heavy rain forced the match to be postponed", the \
implicit causal relationship is: the heavy rain caused the match to be postponed \
(heavy_rain -> match_postponing), even if the graph only has an entity for "the \
match" and no explicit "caused" edge.

Graph so far:
{base_graph}

Respond with ONLY a JSON object of this exact shape, no prose:
{{
  "facts": [
    {{"text": string, "anchors": [entity id, ...], "confidence": number 0-1}}
  ]
}}
Each "text" is one implicit causal relationship stated in natural language. Each \
"anchors" list must name the real entity id(s) from the graph above that this causal \
fact is about -- never invent an entity id that isn't listed. If the text implies no \
causal relation beyond what's already an explicit edge, return an empty "facts" list."""


def run(
    llm: HeuristicLLM, *, nodes: list[GraphNodeRecord], edges: list[GraphEdgeRecord], source_text: str
) -> HeuristicResult:
    base_graph = build_base_graph_text(nodes, edges)
    system = _SYSTEM_TEMPLATE.format(base_graph=base_graph)
    valid_ids = {n.id for n in nodes}
    return run_heuristic(llm, heuristic_type=HEURISTIC_TYPE, system=system, user=source_text, valid_entity_ids=valid_ids)
