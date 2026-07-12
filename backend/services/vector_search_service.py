"""Option A native semantic search (GRAPHITI_INTEGRATION_PLAN.md §4): Neo4j's
own vector index, replacing memory_service's plain CONTAINS text matching
with real cosine-similarity search over entity summaries and chat messages.
No new dependency, no separate database -- just an index and two properties
on the :Entity/:ChatMessage nodes that already exist.
"""

from __future__ import annotations

from dataclasses import dataclass

from db.neo4j_client import Neo4jClient
from llm.embedder import EmbeddingClient

_ENTITY_INDEX = "entity_summary_embedding"
_MESSAGE_INDEX = "chat_message_embedding"


@dataclass(frozen=True)
class VectorHit:
    id: str
    text: str
    score: float


def ensure_indexes(neo4j: Neo4jClient, dimensions: int) -> None:
    neo4j.run(
        f"""
        CREATE VECTOR INDEX {_ENTITY_INDEX} IF NOT EXISTS
        FOR (e:Entity) ON (e.summaryEmbedding)
        OPTIONS {{indexConfig: {{`vector.dimensions`: $dims, `vector.similarity_function`: 'cosine'}}}}
        """,
        dims=dimensions,
    )
    neo4j.run(
        f"""
        CREATE VECTOR INDEX {_MESSAGE_INDEX} IF NOT EXISTS
        FOR (m:ChatMessage) ON (m.contentEmbedding)
        OPTIONS {{indexConfig: {{`vector.dimensions`: $dims, `vector.similarity_function`: 'cosine'}}}}
        """,
        dims=dimensions,
    )


def index_entity_summary(neo4j: Neo4jClient, embedder: EmbeddingClient, *, graph_id: str, entity_id: str, summary: str) -> None:
    if not summary.strip():
        return
    vector = embedder.embed([summary], input_type="passage")[0]
    neo4j.run(
        "MATCH (e:Entity {id: $entity_id, graphId: $graph_id}) SET e.summaryEmbedding = $vector",
        entity_id=entity_id, graph_id=graph_id, vector=vector,
    )


def index_chat_message(neo4j: Neo4jClient, embedder: EmbeddingClient, *, message_id: str, content: str) -> None:
    if not content.strip():
        return
    vector = embedder.embed([content], input_type="passage")[0]
    neo4j.run(
        "MATCH (m:ChatMessage {id: $message_id}) SET m.contentEmbedding = $vector",
        message_id=message_id, vector=vector,
    )


def search_entities(neo4j: Neo4jClient, embedder: EmbeddingClient, *, graph_id: str, query: str, limit: int = 10) -> list[VectorHit]:
    query_vector = embedder.embed([query], input_type="query")[0]
    rows = neo4j.run(
        f"""
        CALL db.index.vector.queryNodes('{_ENTITY_INDEX}', $k, $query_vector)
        YIELD node, score
        WHERE node.graphId = $graph_id
        RETURN node.id AS id, node.summary AS text, score
        ORDER BY score DESC
        LIMIT $limit
        """,
        k=max(limit * 4, limit), query_vector=query_vector, graph_id=graph_id, limit=limit,
    )
    return [VectorHit(id=row["id"], text=row["text"], score=row["score"]) for row in rows]


def search_chat_messages(neo4j: Neo4jClient, embedder: EmbeddingClient, *, graph_id: str, query: str, limit: int = 10) -> list[VectorHit]:
    query_vector = embedder.embed([query], input_type="query")[0]
    rows = neo4j.run(
        f"""
        CALL db.index.vector.queryNodes('{_MESSAGE_INDEX}', $k, $query_vector)
        YIELD node, score
        MATCH (s:ChatSession {{graphId: $graph_id}})-[:HAS_MESSAGE]->(node)
        RETURN node.id AS id, node.content AS text, score
        ORDER BY score DESC
        LIMIT $limit
        """,
        k=max(limit * 4, limit), query_vector=query_vector, graph_id=graph_id, limit=limit,
    )
    return [VectorHit(id=row["id"], text=row["text"], score=row["score"]) for row in rows]
