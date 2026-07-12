"""Runtime-mutable memory-backend config (GRAPHITI_INTEGRATION_PLAN.md §4):
which memory search backend is active (native vs graphiti-core), plus the
Graphiti Neo4j connection and embedding-model override.

Deliberately isolated from services/preferences_store.py -- that store backs
a public `GET /memory/preferences` listing endpoint, and this config holds
real secrets (a Graphiti Neo4j password, an optional embedding API key
override) that must never round-trip through it. `get_status()` is the only
function meant to reach an API response; the raw get_* functions below it are
for internal use (actually connecting) only.
"""

from __future__ import annotations

from dataclasses import dataclass

from db.neo4j_client import Neo4jClient

_VALID_BACKENDS = {"native", "graphiti"}
_NODE_ID = "singleton"


@dataclass(frozen=True)
class GraphitiConnection:
    uri: str
    user: str
    password: str
    database: str


@dataclass(frozen=True)
class EmbeddingOverride:
    base_url: str
    model: str
    api_key: str


@dataclass(frozen=True)
class MemoryBackendStatus:
    backend: str
    graphiti_configured: bool
    graphiti_neo4j_uri: str
    graphiti_neo4j_database: str
    embedding_configured: bool
    embedding_base_url: str
    embedding_model: str


def get_backend(neo4j: Neo4jClient) -> str:
    rows = neo4j.run("MATCH (c:MemoryBackendConfig {id: $id}) RETURN c.backend AS backend", id=_NODE_ID)
    backend = rows[0]["backend"] if rows and rows[0]["backend"] else None
    return backend or "native"


def set_backend(neo4j: Neo4jClient, backend: str) -> None:
    if backend not in _VALID_BACKENDS:
        raise ValueError(f"Unknown memory backend '{backend}'; must be one of {sorted(_VALID_BACKENDS)}")
    neo4j.run(
        "MERGE (c:MemoryBackendConfig {id: $id}) SET c.backend = $backend, c.updatedAt = datetime()",
        id=_NODE_ID, backend=backend,
    )


def save_graphiti_connection(neo4j: Neo4jClient, *, uri: str, user: str, password: str, database: str) -> None:
    neo4j.run(
        """
        MERGE (c:MemoryBackendConfig {id: $id})
        SET c.graphitiUri = $uri, c.graphitiUser = $user, c.graphitiPassword = $password,
            c.graphitiDatabase = $database, c.updatedAt = datetime()
        """,
        id=_NODE_ID, uri=uri, user=user, password=password, database=database,
    )


def get_graphiti_connection(neo4j: Neo4jClient) -> GraphitiConnection | None:
    rows = neo4j.run(
        "MATCH (c:MemoryBackendConfig {id: $id}) RETURN c.graphitiUri AS uri, c.graphitiUser AS user, "
        "c.graphitiPassword AS password, c.graphitiDatabase AS database",
        id=_NODE_ID,
    )
    if not rows or not rows[0]["uri"]:
        return None
    row = rows[0]
    return GraphitiConnection(uri=row["uri"], user=row["user"], password=row["password"], database=row["database"])


def save_embedding_override(neo4j: Neo4jClient, *, base_url: str, model: str, api_key: str) -> None:
    neo4j.run(
        """
        MERGE (c:MemoryBackendConfig {id: $id})
        SET c.embeddingBaseUrl = $base_url, c.embeddingModel = $model, c.embeddingApiKey = $api_key,
            c.updatedAt = datetime()
        """,
        id=_NODE_ID, base_url=base_url, model=model, api_key=api_key,
    )


def get_embedding_override(neo4j: Neo4jClient) -> EmbeddingOverride | None:
    rows = neo4j.run(
        "MATCH (c:MemoryBackendConfig {id: $id}) RETURN c.embeddingBaseUrl AS baseUrl, "
        "c.embeddingModel AS model, c.embeddingApiKey AS apiKey",
        id=_NODE_ID,
    )
    if not rows or not rows[0]["baseUrl"]:
        return None
    row = rows[0]
    return EmbeddingOverride(base_url=row["baseUrl"], model=row["model"], api_key=row["apiKey"])


def get_status(neo4j: Neo4jClient) -> MemoryBackendStatus:
    graphiti = get_graphiti_connection(neo4j)
    embedding = get_embedding_override(neo4j)
    return MemoryBackendStatus(
        backend=get_backend(neo4j),
        graphiti_configured=graphiti is not None,
        graphiti_neo4j_uri=graphiti.uri if graphiti else "",
        graphiti_neo4j_database=graphiti.database if graphiti else "",
        embedding_configured=embedding is not None,
        embedding_base_url=embedding.base_url if embedding else "",
        embedding_model=embedding.model if embedding else "",
    )
