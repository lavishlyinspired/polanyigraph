"""Cross-source memory search (PLAN.md §20 / §2 memory_agent node).

Searches real, already-persisted memory -- chat session history
(services/chat_history_service.py) and entity evolving-summaries
(services/graph_service.py) -- rather than introducing a new store.
Backs the memory_agent LangGraph node and the Memory MCP server's
search_memory tool.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from db.neo4j_client import Neo4jClient
from llm.embedder import EmbeddingClient
from services import graphiti_memory_service, memory_config_service, vector_search_service


@dataclass(frozen=True)
class MemoryHit:
    kind: str  # "chat_message" | "entity_summary"
    id: str
    text: str
    created_at: str | None = None


def _contains_search(neo4j: Neo4jClient, *, graph_id: str, query: str, limit: int) -> list[MemoryHit]:
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
    return [
        MemoryHit(kind="chat_message", id=row["id"], text=row["text"], created_at=row.get("createdAt"))
        for row in message_rows
    ] + [
        MemoryHit(kind="entity_summary", id=row["id"], text=row["text"])
        for row in summary_rows
    ]


def search_memory(
    neo4j: Neo4jClient, *, graph_id: str, query: str, limit: int = 10,
    embedder: EmbeddingClient | None = None, settings: Settings | None = None,
) -> list[MemoryHit]:
    """Dispatches on the runtime-configured memory backend
    (GRAPHITI_INTEGRATION_PLAN.md §4, memory_config_service):

    - "graphiti": real graphiti-core search in its own isolated Neo4j
      database, if a connection has been saved. Requires both embedder and
      settings (to build the client); falls through to the native path
      below if either is missing or no connection is configured yet, so
      flipping the toggle before filling in connection details doesn't
      just return nothing.
    - "native" (default): plain CONTAINS matching, upgraded to hybrid
      vector+text search when an embedder is passed (Option A)."""
    if memory_config_service.get_backend(neo4j) == "graphiti" and embedder is not None and settings is not None:
        connection = memory_config_service.get_graphiti_connection(neo4j)
        if connection is not None:
            client = graphiti_memory_service.get_or_build_client(connection, settings, embedder)
            return [
                MemoryHit(kind="graphiti_fact", id=hit.id, text=hit.fact, created_at=hit.valid_at)
                for hit in client.search(graph_id=graph_id, query=query, limit=limit)
            ]

    hits = _contains_search(neo4j, graph_id=graph_id, query=query, limit=limit)

    if embedder is not None:
        seen_ids = {h.id for h in hits}
        entity_hits = vector_search_service.search_entities(neo4j, embedder, graph_id=graph_id, query=query, limit=limit)
        message_hits = vector_search_service.search_chat_messages(neo4j, embedder, graph_id=graph_id, query=query, limit=limit)
        for hit in entity_hits:
            if hit.id not in seen_ids:
                seen_ids.add(hit.id)
                hits.append(MemoryHit(kind="entity_summary", id=hit.id, text=hit.text))
        for hit in message_hits:
            if hit.id not in seen_ids:
                seen_ids.add(hit.id)
                hits.append(MemoryHit(kind="chat_message", id=hit.id, text=hit.text))

    return hits[:limit]
