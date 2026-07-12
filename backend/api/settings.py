"""GET /settings/connections -- real, non-secret connection info for the
frontend's Connection Center (UI_REFACTOR_PLAN.md). Deliberately excludes
passwords/API keys; only resolved URIs, repo/database names, and tunables
that are already visible from the config file are exposed here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from app.config import Settings, get_settings
from app.dependencies import get_embedder, get_neo4j
from app.schemas import ApiModel
from db.neo4j_client import Neo4jClient
from llm.embedder import EmbeddingClient
from services import graphiti_memory_service, memory_config_service

router = APIRouter(tags=["settings"])


class Neo4jConnectionInfo(ApiModel):
    uri: str
    database: str


class GraphDBConnectionInfo(ApiModel):
    base_url: str
    repository: str


class LlmConnectionInfo(ApiModel):
    base_url: str
    model: str


class ReasoningTunables(ApiModel):
    decay: float
    epsilon: float
    max_iterations: int
    activation_floor: float
    feedback_gain: float


class ConnectionsResponse(ApiModel):
    profile: str
    # Explicit alias: pydantic's to_camel treats the digit->letter boundary in
    # "neo4j" as a word split and produces "neo4J" (see HealthResponse in
    # app/main.py for the same fix).
    neo4j: Neo4jConnectionInfo = Field(alias="neo4j")
    graphdb: GraphDBConnectionInfo
    llm: LlmConnectionInfo
    reasoning: ReasoningTunables
    # Service names only (never credential values) for .env entries that are
    # populated but read by no code path -- see PLAN.md §20.6.
    provisioned_not_wired: list[str]


def _provisioned_not_wired(settings: Settings) -> list[str]:
    checks = {
        "auth0": bool(settings.auth0_client_id or settings.auth0_client_secret or settings.auth0_domain),
        "qdrant": bool(settings.qdrant_cluster_endpoint or settings.odrant_api_key),
        "falkordb": bool(settings.falkor_db_host),
        "zep": bool(settings.zep_api_key),
        "huggingface": bool(settings.hf_token),
    }
    return [name for name, present in checks.items() if present]


@router.get("/settings/connections", response_model=ConnectionsResponse, response_model_by_alias=True)
def get_connections(settings: Settings = Depends(get_settings)) -> ConnectionsResponse:
    return ConnectionsResponse(
        profile=settings.profile,
        neo4j=Neo4jConnectionInfo(uri=settings.neo4j_uri, database=settings.neo4j_database),
        graphdb=GraphDBConnectionInfo(base_url=settings.graphdb_base_url, repository=settings.graphdb_repository),
        llm=LlmConnectionInfo(base_url=settings.llm_base_url, model=settings.nvidia_model),
        reasoning=ReasoningTunables(
            decay=settings.reason_decay,
            epsilon=settings.reason_epsilon,
            max_iterations=settings.reason_max_iterations,
            activation_floor=settings.reason_activation_floor,
            feedback_gain=settings.reason_feedback_gain,
        ),
        provisioned_not_wired=_provisioned_not_wired(settings),
    )


# --- Memory backend (GRAPHITI_INTEGRATION_PLAN.md §4) -----------------------
# Runtime-mutable, unlike everything above (env-file config only) -- these
# endpoints back the Connection Center's "switch backend / connect a
# database and embedding model" UI. Never echo passwords/API keys back.


class MemoryBackendStatusResponse(ApiModel):
    backend: str
    graphiti_configured: bool
    # Explicit aliases: pydantic's to_camel treats the digit->letter boundary
    # in "neo4j" as a word split and produces "Neo4J" (see HealthResponse in
    # app/main.py for the same fix).
    graphiti_neo4j_uri: str = Field(alias="graphitiNeo4jUri")
    graphiti_neo4j_database: str = Field(alias="graphitiNeo4jDatabase")
    embedding_configured: bool
    embedding_base_url: str
    embedding_model: str


def _status_response(neo4j: Neo4jClient) -> MemoryBackendStatusResponse:
    status = memory_config_service.get_status(neo4j)
    return MemoryBackendStatusResponse(
        backend=status.backend,
        graphiti_configured=status.graphiti_configured,
        graphiti_neo4j_uri=status.graphiti_neo4j_uri,
        graphiti_neo4j_database=status.graphiti_neo4j_database,
        embedding_configured=status.embedding_configured,
        embedding_base_url=status.embedding_base_url,
        embedding_model=status.embedding_model,
    )


@router.get("/settings/memory-backend", response_model=MemoryBackendStatusResponse, response_model_by_alias=True)
def get_memory_backend(neo4j: Neo4jClient = Depends(get_neo4j)) -> MemoryBackendStatusResponse:
    return _status_response(neo4j)


class SetMemoryBackendRequest(ApiModel):
    backend: str


@router.put("/settings/memory-backend", response_model=MemoryBackendStatusResponse, response_model_by_alias=True)
def set_memory_backend(request: SetMemoryBackendRequest, neo4j: Neo4jClient = Depends(get_neo4j)) -> MemoryBackendStatusResponse:
    try:
        memory_config_service.set_backend(neo4j, request.backend)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return _status_response(neo4j)


class GraphitiConnectionRequest(ApiModel):
    uri: str
    user: str
    password: str
    database: str


class ConnectionTestResult(ApiModel):
    ok: bool
    error: str | None = None
    status: MemoryBackendStatusResponse


@router.put("/settings/memory-backend/graphiti-connection", response_model=ConnectionTestResult, response_model_by_alias=True)
def set_graphiti_connection(
    request: GraphitiConnectionRequest, neo4j: Neo4jClient = Depends(get_neo4j),
    settings: Settings = Depends(get_settings), embedder: EmbeddingClient = Depends(get_embedder),
) -> ConnectionTestResult:
    # Provision the target database if it doesn't exist yet -- a fresh
    # "connect a database" action should work without the user having run
    # `CREATE DATABASE` by hand first. Only attempted against the *same*
    # Neo4j server (admin rights via the same credentials); a genuinely
    # different server is expected to already have the database.
    try:
        neo4j.run(f"CREATE DATABASE `{request.database}` IF NOT EXISTS")
    except Exception:
        pass  # e.g. a different server, or Community Edition without multi-db -- fall through to the real connectivity test below

    memory_config_service.save_graphiti_connection(
        neo4j, uri=request.uri, user=request.user, password=request.password, database=request.database,
    )

    connection = memory_config_service.get_graphiti_connection(neo4j)
    assert connection is not None  # just saved above
    try:
        client = graphiti_memory_service.get_or_build_client(connection, settings, embedder)
        client.ensure_indices()
        ok, error = True, None
    except Exception as exc:  # noqa: BLE001 - connection test must never 500, report failure instead
        ok, error = False, str(exc)[:300]

    return ConnectionTestResult(ok=ok, error=error, status=_status_response(neo4j))


class EmbeddingOverrideRequest(ApiModel):
    base_url: str
    model: str
    api_key: str


@router.put("/settings/memory-backend/embedding", response_model=ConnectionTestResult, response_model_by_alias=True)
def set_embedding_override(
    request: EmbeddingOverrideRequest, neo4j: Neo4jClient = Depends(get_neo4j),
) -> ConnectionTestResult:
    memory_config_service.save_embedding_override(
        neo4j, base_url=request.base_url, model=request.model, api_key=request.api_key,
    )
    override_settings = Settings(
        embedding_base_url=request.base_url, embedding_model=request.model, embedding_api_key=request.api_key,
    )
    try:
        EmbeddingClient(override_settings).verify()
        ok, error = True, None
    except Exception as exc:  # noqa: BLE001 - connection test must never 500, report failure instead
        ok, error = False, str(exc)[:300]

    return ConnectionTestResult(ok=ok, error=error, status=_status_response(neo4j))
