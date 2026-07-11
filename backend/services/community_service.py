"""Community detection via Neo4j GDS Louvain (PLAN.md §20.4 item 5).

Deferred in the original §20 decision record as "lowest priority, most
speculative value for this product's single-analyst usage pattern" -- built
now on explicit direction, using the real GDS plugin (confirmed installed:
`gds.version()`), not a hand-rolled clustering approximation.

Projects the graph_id-scoped :Entity/:RELATES subgraph into an in-memory GDS
graph via a Cypher projection, runs Louvain, writes `communityId` back onto
each :Entity, then drops the projection (GDS graphs are memory-resident and
must be explicitly released). `gds.graph.project.cypher` is deprecated in
favor of the newer Cypher-projection-as-aggregation-function form as of this
GDS version, but is still functional -- confirmed live against the real
Neo4j Desktop + GDS install this project targets; revisit if a future GDS
version removes it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from db.neo4j_client import Neo4jClient


@dataclass(frozen=True)
class CommunityMember:
    entity_id: str
    label: str
    community_id: int


def detect_communities(neo4j: Neo4jClient, graph_id: str) -> list[CommunityMember]:
    """Runs Louvain and writes the result onto :Entity.communityId, then
    returns the same result get_communities() would read back."""
    if not neo4j.run("MATCH (e:Entity {graphId: $graph_id}) RETURN e LIMIT 1", graph_id=graph_id):
        return []

    projection_name = f"community-{uuid.uuid4().hex[:12]}"
    neo4j.run(
        """
        CALL gds.graph.project.cypher(
          $projection_name,
          'MATCH (e:Entity {graphId: $graph_id}) RETURN id(e) AS id',
          'MATCH (s:Entity {graphId: $graph_id})-[r:RELATES {graphId: $graph_id}]->(t:Entity {graphId: $graph_id}) RETURN id(s) AS source, id(t) AS target',
          {parameters: {graph_id: $graph_id}}
        )
        """,
        projection_name=projection_name,
        graph_id=graph_id,
    )
    try:
        neo4j.run(
            "CALL gds.louvain.write($projection_name, {writeProperty: 'communityId'})",
            projection_name=projection_name,
        )
    finally:
        neo4j.run("CALL gds.graph.drop($projection_name)", projection_name=projection_name)

    return get_communities(neo4j, graph_id)


def get_communities(neo4j: Neo4jClient, graph_id: str) -> list[CommunityMember]:
    """Reads the last-computed communityId assignment without recomputing."""
    rows = neo4j.run(
        """
        MATCH (e:Entity {graphId: $graph_id})
        WHERE e.communityId IS NOT NULL
        RETURN e.id AS entityId, e.label AS label, e.communityId AS communityId
        ORDER BY e.communityId, e.label
        """,
        graph_id=graph_id,
    )
    return [
        CommunityMember(entity_id=r["entityId"], label=r["label"], community_id=r["communityId"])
        for r in rows
    ]
