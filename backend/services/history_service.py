"""Ingest history: what was posted, when, and what it produced.

Previously every ingest wrote the same generic sourceDoc label
("pasted-text:{graph_id}") with the actual text stored nowhere, so nothing
could be reviewed after the fact. This gives each ingest a real event record
with the full posted text, so a graph accumulating documents over multiple
sessions has a reviewable trail.
"""

from __future__ import annotations

from dataclasses import dataclass

from db.neo4j_client import Neo4jClient


@dataclass(frozen=True)
class IngestEventRecord:
    id: str
    text: str
    entity_count: int
    relationship_count: int
    dropped_count: int
    created_at: str


def record_ingest_event(
    neo4j: Neo4jClient,
    *,
    graph_id: str,
    event_id: str,
    text: str,
    entity_count: int,
    relationship_count: int,
    dropped_count: int,
    entity_ids: list[str] = (),
) -> None:
    """PLAN.md §20 item 1: also links IngestEvent-[:PRODUCED]->Entity for every
    entity this ingest touched, so provenance is a real graph traversal instead
    of the sourceDoc free-text field."""
    neo4j.run(
        """
        CREATE (h:IngestEvent {
          id: $event_id, graphId: $graph_id, text: $text,
          entityCount: $entity_count, relationshipCount: $relationship_count,
          droppedCount: $dropped_count, createdAt: datetime()
        })
        WITH h
        UNWIND $entity_ids AS eid
        MATCH (e:Entity {id: eid, graphId: $graph_id})
        MERGE (h)-[:PRODUCED]->(e)
        """,
        event_id=event_id,
        graph_id=graph_id,
        text=text,
        entity_count=entity_count,
        relationship_count=relationship_count,
        dropped_count=dropped_count,
        entity_ids=list(entity_ids),
    )


def get_produced_entity_ids(neo4j: Neo4jClient, *, graph_id: str, event_id: str) -> list[str]:
    rows = neo4j.run(
        """
        MATCH (h:IngestEvent {id: $event_id, graphId: $graph_id})-[:PRODUCED]->(e:Entity)
        RETURN e.id AS id
        """,
        event_id=event_id,
        graph_id=graph_id,
    )
    return [row["id"] for row in rows]


def get_entity_provenance(neo4j: Neo4jClient, *, graph_id: str, entity_id: str) -> list["IngestEventRecord"]:
    """Every ingest event that produced/touched this entity (UI_PLAN.md §9.1)."""
    rows = neo4j.run(
        """
        MATCH (h:IngestEvent {graphId: $graph_id})-[:PRODUCED]->(e:Entity {id: $entity_id, graphId: $graph_id})
        RETURN h.id AS id, h.text AS text, h.entityCount AS entityCount,
               h.relationshipCount AS relationshipCount, h.droppedCount AS droppedCount,
               toString(h.createdAt) AS createdAt
        ORDER BY h.createdAt DESC
        """,
        graph_id=graph_id,
        entity_id=entity_id,
    )
    return [
        IngestEventRecord(
            id=r["id"], text=r["text"],
            entity_count=r["entityCount"], relationship_count=r["relationshipCount"],
            dropped_count=r["droppedCount"], created_at=r["createdAt"],
        )
        for r in rows
    ]


def list_ingest_events(neo4j: Neo4jClient, graph_id: str) -> list[IngestEventRecord]:
    rows = neo4j.run(
        """
        MATCH (h:IngestEvent {graphId: $graph_id})
        RETURN h.id AS id, h.text AS text, h.entityCount AS entityCount,
               h.relationshipCount AS relationshipCount, h.droppedCount AS droppedCount,
               toString(h.createdAt) AS createdAt
        ORDER BY h.createdAt DESC
        """,
        graph_id=graph_id,
    )
    return [
        IngestEventRecord(
            id=r["id"], text=r["text"],
            entity_count=r["entityCount"], relationship_count=r["relationshipCount"],
            dropped_count=r["droppedCount"], created_at=r["createdAt"],
        )
        for r in rows
    ]
