"""Analytics Role Mapping: a small universal role taxonomy (actor/event/
value/temporal/metadata) mapped per-ontology-repository onto real ontology
"anchor" classes, used to weight noisy nodes out of centrality-style
analytics (PLAN Phase 1, follow-up work agreed 2026-07-14).

Fixes a real gap found via live testing: extracted date/percentage entities
(e.g. "8.45%", "August 5, 2026") were dominating degree_centrality's "most
central entity" rankings in the live FIBO-backed graph purely by co-occurring
with every fact that cites a rate or a date -- not because they're actually
central subject matter. A handful of high-level ontology anchors is enough:
any class that IS-A an anchor (reflexively or transitively, via the same
OntologySchema.build_subclass_matcher() reasoning already uses) inherits its
role, so a single "quantity value" anchor covers percentage, ratio value,
monetary amount, and every other FIBO value subtype without enumerating them.

Deliberately fails open: an ontology repository with no configured anchors,
or a node type that doesn't resolve to any known role, is left unweighted
(1.0) -- current behavior is the safe default, matching
build_domain_range_matcher()'s fails-open pattern for unknown properties.
"""

from __future__ import annotations

from enum import Enum
from typing import Callable

import networkx as nx

from ontology.schema import OntologySchema


class AnalyticsRole(str, Enum):
    ACTOR = "actor"
    EVENT = "event"
    VALUE = "value"
    TEMPORAL = "temporal"
    METADATA = "metadata"


# Applied as a multiplier on a node's raw algorithm score -- not a graph-
# structure change -- so path-based algorithms (betweenness) still route
# through Value/Temporal nodes correctly if the real topology needs to; only
# the reported "importance" of those nodes is suppressed.
DEFAULT_ROLE_WEIGHT: dict[AnalyticsRole, float] = {
    AnalyticsRole.ACTOR: 1.0,
    AnalyticsRole.EVENT: 1.0,
    AnalyticsRole.VALUE: 0.0,
    AnalyticsRole.TEMPORAL: 0.0,
    AnalyticsRole.METADATA: 0.0,
}

# Anchor classes, per ontology repository: any class that is this class or a
# transitive rdfs:subClassOf descendant of it inherits its role. Confirmed
# against the live FIBO repository (2026-07-14 investigation): "rate of
# return"/"monetary amount" -> quantity value; "time of day"/"date" ->
# time instant -- covers every noisy entity type found via live analytics
# runs with just these two anchors.
ROLE_ANCHORS_BY_REPOSITORY: dict[str, dict[str, AnalyticsRole]] = {
    "fibo": {
        "quantity value": AnalyticsRole.VALUE,
        "time instant": AnalyticsRole.TEMPORAL,
    },
}


def build_role_resolver(
    schema: OntologySchema, anchors: dict[str, AnalyticsRole]
) -> Callable[[str], AnalyticsRole | None]:
    """Builds the subclass matcher once; the returned closure is cheap to
    call per node."""
    matches = schema.build_subclass_matcher()

    def resolve(node_type: str) -> AnalyticsRole | None:
        if not node_type:
            return None
        for anchor_label, role in anchors.items():
            if matches(node_type, anchor_label):
                return role
        return None

    return resolve


def resolver_for_repository(schema: OntologySchema) -> Callable[[str], AnalyticsRole | None]:
    anchors = ROLE_ANCHORS_BY_REPOSITORY.get(schema.repository, {})
    return build_role_resolver(schema, anchors)


def apply_role_weights(
    scores: dict[str, float],
    graph: nx.DiGraph,
    resolve_role: Callable[[str], AnalyticsRole | None],
    role_weights: dict[AnalyticsRole, float] = DEFAULT_ROLE_WEIGHT,
) -> dict[str, float]:
    weighted: dict[str, float] = {}
    for node_id, score in scores.items():
        node_type = graph.nodes[node_id].get("type", "") if node_id in graph.nodes else ""
        role = resolve_role(node_type)
        weight = role_weights.get(role, 1.0) if role is not None else 1.0
        weighted[node_id] = score * weight
    return weighted


def apply_role_weights_if_centrality(
    scores: dict[str, float],
    graph: nx.DiGraph,
    category: str,
    schema: OntologySchema | None,
) -> dict[str, float]:
    """Single seam both services/analytics_service.py and api/analytics.py
    call, so "should this result be role-weighted" is decided in exactly
    one place. Scoped to category == "centrality" per the agreed design --
    community/pathfinding/similarity/classification results aren't a ranked
    "most important entity" list, so role noise doesn't apply the same way."""
    if category != "centrality" or schema is None:
        return scores
    resolve_role = resolver_for_repository(schema)
    return apply_role_weights(scores, graph, resolve_role)
