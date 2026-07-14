"""Community detection via the networkx-based analytics engine (PLAN.md
§20.4 item 5; migrated off Neo4j GDS per plans/analytical-engine.md Slice 3).

Originally ran Neo4j GDS Louvain via `gds.graph.project.cypher` +
`gds.louvain.write`. Migrated because that call path hard-depended on the
GDS plugin being installed and separately confirmed live (`gds.version()`),
and because `gds.graph.project.cypher` itself emits a live deprecation
warning on every call ("replaced by gds.graph.project Cypher projection as
an aggregation function") -- both a real deployment risk and a ticking
upstream-removal risk. Louvain now runs in-process via
analytics.algorithms.community.louvain_communities (networkx) against a
plain in-memory projection; only the write-back target is unchanged
(:Entity.communityId), so detect_communities/get_communities/CommunityMember
and every caller of them keep their exact same contract.
"""

from __future__ import annotations

from dataclasses import dataclass

from analytics.algorithms.community import louvain_communities
from analytics.projection import NamedProjection, build_graph
from analytics.store import Neo4jGraphStore
from db.neo4j_client import Neo4jClient
from services import graph_service


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

    record = graph_service.get_graph(neo4j, graph_id)
    projection = NamedProjection(name=f"community-{graph_id}", graph_id=graph_id, graph=build_graph(record.nodes, record.edges))
    community_ids = louvain_communities(projection.graph)

    Neo4jGraphStore(neo4j).write_scores(projection, "communityId", community_ids)

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
