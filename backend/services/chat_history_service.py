"""Chat session memory (PLAN.md §20 item 4, Zep/Graphiti-inspired, rebuilt natively).

POST /chat was stateless -- every call rebuilt the system prompt from scratch
with no memory of prior turns in the same conversation. This gives each
session a real, ordered message history, mirroring Zep's
memory.add()/memory.get() without any dependency on graphiti-core or the Zep
API (see PLAN.md §20.6 -- rebuild natively, no dependency).
"""

from __future__ import annotations

from dataclasses import dataclass

from db.neo4j_client import Neo4jClient


@dataclass(frozen=True)
class ChatMessageRecord:
    role: str
    content: str
    created_at: str


def append_message(
    neo4j: Neo4jClient,
    *,
    graph_id: str,
    session_id: str,
    message_id: str,
    role: str,
    content: str,
) -> None:
    neo4j.run(
        """
        MERGE (s:ChatSession {id: $session_id, graphId: $graph_id})
        WITH s
        OPTIONAL MATCH (s)-[:HAS_MESSAGE]->(existing:ChatMessage)
        WITH s, count(existing) AS seq
        CREATE (m:ChatMessage {id: $message_id, role: $role, content: $content, seq: seq, createdAt: datetime()})
        MERGE (s)-[:HAS_MESSAGE]->(m)
        """,
        graph_id=graph_id,
        session_id=session_id,
        message_id=message_id,
        role=role,
        content=content,
    )


def get_recent_messages(
    neo4j: Neo4jClient, *, graph_id: str, session_id: str, limit: int = 10
) -> list[ChatMessageRecord]:
    """Most recent `limit` messages, returned oldest-first (chronological, ready
    to drop straight into a prompt)."""
    rows = neo4j.run(
        """
        MATCH (s:ChatSession {id: $session_id, graphId: $graph_id})-[:HAS_MESSAGE]->(m:ChatMessage)
        RETURN m.role AS role, m.content AS content, toString(m.createdAt) AS createdAt
        ORDER BY m.seq DESC
        LIMIT $limit
        """,
        graph_id=graph_id,
        session_id=session_id,
        limit=limit,
    )
    return list(
        reversed(
            [ChatMessageRecord(role=r["role"], content=r["content"], created_at=r["createdAt"]) for r in rows]
        )
    )
