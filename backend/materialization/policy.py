"""Semantic Materialization Engine -- decision layer (PLAN Phase 3, .claude/
docs/research/2026-07-14-semantic-materialization-engine-design.md). Pure
function: ontology role (Phase 1's analytics.roles resolver, reused
unchanged) + a fan-out-based workload signal -> a single storage decision.
No I/O -- callers assemble the fan-out map and introducing relationship
from an already-loaded ExtractionResult, so this stays unit-testable
without a live Neo4j/GraphDB.

v1 scope (see design doc's Non-goals): only NODE and PROPERTY are ever
decided here. SHARED_NODE/EVENT_NODE/EMBEDDED_OBJECT/TIME_NODE remain
defined in MaterializationPolicy for forward compatibility with the design
doc, but nothing constructs them yet -- there's no evidenced need for them
in this codebase today. The only real, live-verified problem this closes
is a Value/Temporal/Metadata-role leaf value (a percentage, a date) that's
the target or source of exactly one relationship and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from analytics.roles import AnalyticsRole
from extraction.pipeline import ExtractedEntity, ExtractedRelationship

_INLINABLE_ROLES = frozenset({AnalyticsRole.VALUE, AnalyticsRole.TEMPORAL, AnalyticsRole.METADATA})


class MaterializationPolicy(str, Enum):
    NODE = "node"
    PROPERTY = "property"
    SHARED_NODE = "shared_node"
    EVENT_NODE = "event_node"
    EMBEDDED_OBJECT = "embedded_object"
    TIME_NODE = "time_node"


@dataclass(frozen=True)
class MaterializationDecision:
    policy: MaterializationPolicy
    # PROPERTY only: which entity (by extracted name, not yet a Neo4j id)
    # the value attaches to, and under which property key.
    attach_to_entity_name: str | None = None
    property_key: str | None = None
    reason: str = ""


def plan_materialization(
    entity: ExtractedEntity,
    role: AnalyticsRole | None,
    fanout: int,
    introducing_relationship: ExtractedRelationship | None,
) -> MaterializationDecision:
    if role in _INLINABLE_ROLES and fanout == 1 and introducing_relationship is not None:
        other = (
            introducing_relationship.source
            if introducing_relationship.target == entity.name
            else introducing_relationship.target
        )
        if other != entity.name:
            return MaterializationDecision(
                policy=MaterializationPolicy.PROPERTY,
                attach_to_entity_name=other,
                property_key=introducing_relationship.relation,
                reason=f"role={role.value}, fanout=1, inlined via '{introducing_relationship.relation}'",
            )

    reason = "no role resolved" if role is None else f"role={role.value}, fanout={fanout}"
    return MaterializationDecision(policy=MaterializationPolicy.NODE, reason=reason)


def compute_fanout(relationships: list[ExtractedRelationship]) -> dict[str, int]:
    fanout: dict[str, int] = {}
    for rel in relationships:
        fanout[rel.source] = fanout.get(rel.source, 0) + 1
        fanout[rel.target] = fanout.get(rel.target, 0) + 1
    return fanout


def find_introducing_relationship(
    entity_name: str, relationships: list[ExtractedRelationship]
) -> ExtractedRelationship | None:
    for rel in relationships:
        if rel.source == entity_name or rel.target == entity_name:
            return rel
    return None
