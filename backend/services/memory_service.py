"""Cross-source memory search (PLAN.md §20 / §2 memory_agent node).

Searches real, already-persisted memory -- chat session history
(services/chat_history_service.py) and entity evolving-summaries
(services/graph_service.py) -- rather than introducing a new store.
Backs the memory_agent LangGraph node and the Memory MCP server's
search_memory tool.
"""

from __future__ import annotations

from dataclasses import dataclass

from db.neo4j_client import Neo4jClient


@dataclass(frozen=True)
class MemoryHit:
    kind: str  # "chat_message" | "entity_summary"
    id: str
    text: str
    created_at: str | None = None


def search_memory(neo4j: Neo4jClient, *, graph_id: str, query: str, limit: int = 10) -> list[MemoryHit]:
    message_rows = neo4j.run(
        """
        MATCH (s:ChatSession {graphId: $graph_id})-[:HAS_MESSAGE]->(m:ChatMessage)
        WHERE toLower(m.content) CONTAINS toLower($search_text)
        RETURN m.id AS id, m.content AS text, toString(m.createdAt) AS createdAt
        ORDER BY m.seq DESC
        LIMIT $limit
        """,
        graph_id=graph_id,
        search_text=query,
        limit=limit,
    )
    summary_rows = neo4j.run(
        """
        MATCH (e:Entity {graphId: $graph_id})
        WHERE e.summary IS NOT NULL AND toLower(e.summary) CONTAINS toLower($search_text)
        RETURN e.id AS id, e.summary AS text
        LIMIT $limit
        """,
        graph_id=graph_id,
        search_text=query,
        limit=limit,
    )
    hits = [
        MemoryHit(kind="chat_message", id=row["id"], text=row["text"], created_at=row.get("createdAt"))
        for row in message_rows
    ] + [
        MemoryHit(kind="entity_summary", id=row["id"], text=row["text"])
        for row in summary_rows
    ]
    return hits[:limit]
