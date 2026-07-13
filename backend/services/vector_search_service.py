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
    type: str | None = None


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


def find_similar_entities(
    neo4j: Neo4jClient, *, graph_id: str, entity_id: str, limit: int = 10, min_score: float = 0.5,
) -> list[VectorHit]:
    """2026-07-13 plan §11.2 (entity resolution): candidate retrieval over
    entities already indexed for search_entities -- no new embedding call,
    reuses summaryEmbedding. Same graph, excludes the entity itself.

    Deliberately NOT filtered by exact type match in Cypher (a prior
    version was, and live-verifying against a real LLM's extraction found a
    real gap: the same real company got "stock corporation" from one
    document's extraction and "corporation" from another's -- different
    FIBO subtype labels, same real-world entity, so an exact-string type
    filter silently excluded a genuine duplicate). Callers needing type
    compatibility should apply an ontology-aware check (e.g.
    OntologySchema.build_subclass_matcher()) on the returned .type field
    themselves -- this function returns type, doesn't filter on it.

    min_score is a loose sanity floor (well below any real duplicate-
    decision threshold), not the actual duplicate cutoff -- see
    services/entity_resolution_service.py for why: empirically, pure cosine
    similarity over full summaries doesn't cleanly separate "same entity,
    different wording" from "different entity, similar summary structure,"
    so the real precision filter is a deterministic label-token check
    layered on top of these candidates, not a stricter score here."""
    rows = neo4j.run(
        f"""
        MATCH (e:Entity {{id: $entity_id, graphId: $graph_id}})
        WHERE e.summaryEmbedding IS NOT NULL
        CALL db.index.vector.queryNodes('{_ENTITY_INDEX}', $k, e.summaryEmbedding)
        YIELD node, score
        WHERE node.graphId = $graph_id AND node.id <> $entity_id AND score >= $min_score
        RETURN node.id AS id, node.label AS text, node.type AS type, score
        ORDER BY score DESC
        LIMIT $limit
        """,
        entity_id=entity_id, graph_id=graph_id,
        k=max(limit * 4, limit), min_score=min_score, limit=limit,
    )
    return [VectorHit(id=row["id"], text=row["text"], score=row["score"], type=row["type"]) for row in rows]


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
