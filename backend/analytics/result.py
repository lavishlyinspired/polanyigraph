"""AlgorithmResult: the uniform return shape every analytics algorithm
produces, ephemeral by default, persisted only when a caller opts in via
.persist(store, property_name) (PLAN: plans/analytical-engine.md Slice 1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from analytics.projection import NamedProjection
    from analytics.store import GraphStore

ChartType = Literal["bar", "table", "distribution"]


@dataclass(frozen=True)
class AlgorithmResult:
    algorithm: str
    projection: "NamedProjection"
    node_scores: dict[str, float]
    metadata: dict[str, Any] = field(default_factory=dict)
    suggested_chart: ChartType | None = None

    def persist(self, store: "GraphStore", property_name: str) -> None:
        store.write_scores(self.projection, property_name, self.node_scores)
