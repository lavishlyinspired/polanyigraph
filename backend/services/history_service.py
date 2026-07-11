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
) -> None:
    neo4j.run(
        """
        CREATE (h:IngestEvent {
          id: $event_id, graphId: $graph_id, text: $text,
          entityCount: $entity_count, relationshipCount: $relationship_count,
          droppedCount: $dropped_count, createdAt: datetime()
        })
        """,
        event_id=event_id,
        graph_id=graph_id,
        text=text,
        entity_count=entity_count,
        relationship_count=relationship_count,
        dropped_count=dropped_count,
    )


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
