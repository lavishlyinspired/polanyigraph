"""Presuppositions heuristic (PLAN.md §19.1/§19.6 step 4).

Paper's definition (§3.2): "Presuppositions are implicit assumptions necessary
for statements to be meaningful... For example, the statement 'The athlete won
the gold medal' presupposes that there was a competition, possibly an
Olympic one, illustrating how presuppositions convey information beyond the
explicit content of a statement."
"""

from __future__ import annotations

from enrichment.heuristics.base import HeuristicLLM, HeuristicResult, build_base_graph_text, run_heuristic
from services.graph_service import GraphEdgeRecord, GraphNodeRecord

HEURISTIC_TYPE = "presupposition"

_SYSTEM_TEMPLATE = """You are an expert ontology engineer extending a knowledge graph with \
implicit knowledge. Task: identify Presuppositions -- implicit assumptions necessary for a \
statement in the source text to be meaningful, that are NOT already explicit entities or \
edges in the graph below.

Example: the statement "The athlete won the gold medal" presupposes that there was a \
competition, possibly an Olympic one -- information conveyed beyond the explicit content \
of the statement.

Graph so far:
{base_graph}

Respond with ONLY a JSON object of this exact shape, no prose:
{{
  "facts": [
    {{"text": string, "anchors": [entity id, ...], "confidence": number 0-1}}
  ]
}}
Each "text" is one implicit presupposition stated in natural language. Each "anchors" \
list must name the real entity id(s) from the graph above that this presupposition is \
about -- never invent an entity id that isn't listed. If the text carries no presupposition \
beyond what's already explicit, return an empty "facts" list."""


def run(
    llm: HeuristicLLM, *, nodes: list[GraphNodeRecord], edges: list[GraphEdgeRecord], source_text: str
) -> HeuristicResult:
    base_graph = build_base_graph_text(nodes, edges)
    system = _SYSTEM_TEMPLATE.format(base_graph=base_graph)
    valid_ids = {n.id for n in nodes}
    return run_heuristic(llm, heuristic_type=HEURISTIC_TYPE, system=system, user=source_text, valid_entity_ids=valid_ids)
