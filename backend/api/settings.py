"""GET /settings/connections -- real, non-secret connection info for the
frontend's Connection Center (UI_REFACTOR_PLAN.md). Deliberately excludes
passwords/API keys; only resolved URIs, repo/database names, and tunables
that are already visible from the config file are exposed here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import Field

from app.config import Settings, get_settings
from app.schemas import ApiModel

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
