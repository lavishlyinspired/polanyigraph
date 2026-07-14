"""GraphStore: write-back interface for AlgorithmResult.persist() (PLAN:
plans/analytical-engine.md Slice 1). Neo4jGraphStore is the only
implementation -- it exists because AlgorithmResult.persist() needs
something to call that isn't a bare Neo4jClient, and because a fake
implementation of this same small interface is what test_analytics_result.py
uses to test .persist() without a live DB.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from db.neo4j_client import Neo4jClient

if TYPE_CHECKING:
    from analytics.projection import NamedProjection


class GraphStore(Protocol):
    def write_scores(self, projection: "NamedProjection", property_name: str, scores: dict[str, float]) -> None: ...


class Neo4jGraphStore:
    def __init__(self, neo4j: Neo4jClient) -> None:
        self._neo4j = neo4j

    def write_scores(self, projection: "NamedProjection", property_name: str, scores: dict[str, float]) -> None:
        for node_id, score in scores.items():
            self._neo4j.run(
                "MATCH (e:Entity {id: $id, graphId: $graph_id}) SET e[$prop] = $score",
                id=node_id,
                graph_id=projection.graph_id,
                prop=property_name,
                score=score,
            )
