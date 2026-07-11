"""Image Schemas heuristic (PLAN.md §19.1/§19.6 step 4).

Paper's definition (§3.2, Johnson 1987; Lakoff et al. 1999): "Image schemas
are fundamental cognitive structures that help humans organize and interpret
their experiences of the world... such as container, path, balance, and
force... For example, the container schema helps us understand phrases like
'in the competition' or 'out of the box', while the path schema underlies our
comprehension of sentences describing movement or progress."
"""

from __future__ import annotations

from enrichment.heuristics.base import HeuristicLLM, HeuristicResult, build_base_graph_text, run_heuristic
from services.graph_service import GraphEdgeRecord, GraphNodeRecord

HEURISTIC_TYPE = "image_schema"

_SYSTEM_TEMPLATE = """You are an expert ontology engineer extending a knowledge graph with \
implicit knowledge. Task: identify Image Schemas -- embodied cognitive structures (container, \
path, balance, force) underlying the source text's spatial/conceptual meaning, that are NOT \
already explicit in the graph below.

Example: the container schema helps explain phrases like "in the competition" or "out of the \
box"; the path schema underlies sentences describing movement or progress.

Graph so far:
{base_graph}

Respond with ONLY a JSON object of this exact shape, no prose:
{{
  "facts": [
    {{"text": string, "anchors": [entity id, ...], "confidence": number 0-1}}
  ]
}}
Each "text" is one implicit cognitive/spatial structure stated in natural language (name \
the schema, e.g. "container", "path", "force", "balance", and what it structures). Each \
"anchors" list must name the real entity id(s) from the graph above this schema is about \
-- never invent an entity id that isn't listed. If no image schema is implied, return an \
empty "facts" list."""


def run(
    llm: HeuristicLLM, *, nodes: list[GraphNodeRecord], edges: list[GraphEdgeRecord], source_text: str
) -> HeuristicResult:
    base_graph = build_base_graph_text(nodes, edges)
    system = _SYSTEM_TEMPLATE.format(base_graph=base_graph)
    valid_ids = {n.id for n in nodes}
    return run_heuristic(llm, heuristic_type=HEURISTIC_TYPE, system=system, user=source_text, valid_entity_ids=valid_ids)
