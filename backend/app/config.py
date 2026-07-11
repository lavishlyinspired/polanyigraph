"""Application configuration.

Domain-agnostic and provider-agnostic: nothing here hardcodes FIBO or a specific
LLM vendor. The ontology repository and the LLM model are both configuration.

Two graph backends (per the confirmed stack):
  * Neo4j (LPG)      -> instance graph, spread-activation reasoning, visualization
  * Ontotext GraphDB -> ontology (RDF/OWL) + SPARQL; the source of entity TYPES

Profiles select desktop (local) vs cloud connection details. Default: desktop.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qs, urlparse

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

Profile = Literal["desktop", "cloud"]

# Absolute path to the repo-root .env, independent of CWD at process launch —
# relative paths broke when dev.sh starts uvicorn from backend/ (CWD=backend
# means "../docs/.env" and ".env" both miss the root .env).
_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    profile: Profile = Field(default="desktop")

    # --- Neo4j (LPG) ---
    neo4j_uri_desktop: str = Field(default="bolt://localhost:7687")
    neo4j_db_user_desktop: str = Field(default="neo4j")
    neo4j_db_password_desktop: str = Field(default="")
    neo4j_db_desktop: str = Field(default="neo4j")

    neo4j_connection_uri_cloud: str = Field(default="")
    neo4j_username_cloud: str = Field(default="")
    neo4j_password_cloud: str = Field(default="")
    neo4j_database_cloud: str = Field(default="")

    # --- Ontotext GraphDB (RDF/SPARQL) ---
    ontotext_db_repo_url_desktop: str = Field(default="http://localhost:7200/?repositoryId=fibo")
    ontotext_db_url_cloud: str = Field(default="")
    ontotext_db_username_cloud: str = Field(default="")
    ontotext_db_password_cloud: str = Field(default="")

    # --- LLM (OpenAI-compatible; NVIDIA-hosted GLM by default) ---
    llm_base_url: str = Field(default="https://integrate.api.nvidia.com/v1")
    nvidia_api_key: str = Field(default="")
    # z-ai/glm-5.2 is listed in the NVIDIA catalog but hangs indefinitely on
    # /chat/completions in this environment (confirmed via direct curl: 30s+,
    # zero bytes back), while this model responds in ~0.3s on the same
    # key/endpoint. Swap back once glm-5.2 availability is confirmed working.
    nvidia_model: str = Field(default="meta/llama-3.1-8b-instruct")

    # --- Reasoning parameters (all tunable; no magic numbers in the engine) ---
    reason_decay: float = Field(default=0.45)
    reason_epsilon: float = Field(default=1e-3)
    reason_max_iterations: int = Field(default=10)
    reason_activation_floor: float = Field(default=0.01)

    # --- Neo4j resolved views -------------------------------------------------
    @property
    def neo4j_uri(self) -> str:
        return self.neo4j_connection_uri_cloud if self.profile == "cloud" else self.neo4j_uri_desktop

    @property
    def neo4j_user(self) -> str:
        return self.neo4j_username_cloud if self.profile == "cloud" else self.neo4j_db_user_desktop

    @property
    def neo4j_password(self) -> str:
        return self.neo4j_password_cloud if self.profile == "cloud" else self.neo4j_db_password_desktop

    @property
    def neo4j_database(self) -> str:
        return self.neo4j_database_cloud if self.profile == "cloud" else self.neo4j_db_desktop

    # --- GraphDB resolved views ----------------------------------------------
    @property
    def graphdb_base_url(self) -> str:
        if self.profile == "cloud":
            return self.ontotext_db_url_cloud.rstrip("/")
        parsed = urlparse(self.ontotext_db_repo_url_desktop)
        return f"{parsed.scheme}://{parsed.netloc}"

    @property
    def graphdb_repository(self) -> str:
        """Repository id parsed from the configured URL. Domain-agnostic: swap the
        repo to swap the ontology (fibo, cco, schema.org, a bio-ontology, ...)."""
        parsed = urlparse(self.ontotext_db_repo_url_desktop)
        repo = parse_qs(parsed.query).get("repositoryId", [""])[0]
        return repo or "fibo"

    @property
    def graphdb_sparql_endpoint(self) -> str:
        return f"{self.graphdb_base_url}/repositories/{self.graphdb_repository}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
