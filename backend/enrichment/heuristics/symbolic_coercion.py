"""Symbolic Coercion heuristic (PLAN.md §19.1/§19.6 step 4).

Paper's definition (§3.2, Peircean semiotics -- Peirce & Buchler, 1955):
"Symbolic coercions involve the transformation of literal meanings into
symbolic interpretations... particularly in domains where abstract ideas are
often expressed through concrete objective correlatives." The paper's own
worked example text is truncated in the extracted source (sports commentary,
a national team's animal nickname), so the few-shot below is a faithful
reconstruction of the same Peircean pattern it illustrates: a literal term
standing in for a symbolic referent.
"""

from __future__ import annotations

from enrichment.heuristics.base import HeuristicLLM, HeuristicResult, build_base_graph_text, run_heuristic
from services.graph_service import GraphEdgeRecord, GraphNodeRecord

HEURISTIC_TYPE = "symbolic_coercion"

_SYSTEM_TEMPLATE = """You are an expert ontology engineer extending a knowledge graph with \
implicit knowledge. Task: identify Symbolic Coercion (Peircean semiotics) -- where a \
literal term in the source text is transformed into a symbolic interpretation standing for \
something larger than its literal referent, not already captured as an explicit entity or \
edge in the graph below.

Example: in sport commentary, a national team's animal nickname (e.g. "the Kangaroos") is \
used literally as an animal name but symbolically represents the national team and, by \
extension, national pride -- a concrete objective correlative standing in for an abstract idea.

Graph so far:
{base_graph}

Respond with ONLY a JSON object of this exact shape, no prose:
{{
  "facts": [
    {{"text": string, "anchors": [entity id, ...], "confidence": number 0-1}}
  ]
}}
Each "text" is one symbolic interpretation stated in natural language (name the literal \
term and what it symbolically represents). Each "anchors" list must name the real entity \
id(s) from the graph above this symbolism is about -- never invent an entity id that isn't \
listed. The example above ("the Kangaroos") is illustrative only -- do not repeat it or any \
part of it in your output unless it verbatim appears in the source text below. If the \
source text contains no symbolic coercion of its own, return an empty "facts" list."""


def run(
    llm: HeuristicLLM, *, nodes: list[GraphNodeRecord], edges: list[GraphEdgeRecord], source_text: str
) -> HeuristicResult:
    base_graph = build_base_graph_text(nodes, edges)
    system = _SYSTEM_TEMPLATE.format(base_graph=base_graph)
    valid_ids = {n.id for n in nodes}
    return run_heuristic(llm, heuristic_type=HEURISTIC_TYPE, system=system, user=source_text, valid_entity_ids=valid_ids)
