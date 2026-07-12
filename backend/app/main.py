"""FastAPI application entrypoint.

MVP surface (see docs/MVP_PLAN.md): health + ingest + graph + reason + query.
On startup, ontology constraints are mirrored into Neo4j (idempotent) so the
instance store is ready before any ingest.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pydantic import Field

from app.config import get_settings
from app.schemas import ApiModel


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.dependencies import get_embedder, get_neo4j
    from ontology.sync import ensure_constraints
    from services import vector_search_service

    try:
        ensure_constraints(get_neo4j())
    except Exception:
        # Neo4j may be down at boot; /health surfaces this. Don't crash startup.
        pass
    try:
        vector_search_service.ensure_indexes(get_neo4j(), dimensions=get_embedder().dimensions)
    except Exception:
        # Same as above -- Neo4j may be down, or the vector index feature may
        # be unavailable on an older Neo4j; /settings/connections surfaces
        # embedding status separately. Don't crash startup either way.
        pass
    yield


app = FastAPI(title="Neurosymbolic KG (domain-agnostic)", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _probe(fn) -> dict[str, object]:
    try:
        fn()
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001 - health must never raise
        return {"ok": False, "error": type(exc).__name__ + ": " + str(exc)[:200]}


class ServiceStatus(ApiModel):
    ok: bool
    error: str | None = None


class LlmStatus(ServiceStatus):
    model: str


class HealthResponse(ApiModel):
    status: str
    profile: str
    ontology_repository: str
    # Explicit alias: pydantic's to_camel treats the digit->letter boundary in
    # "neo4j" as a word split and produces "neo4J", breaking the frontend
    # contract (api.ts expects "neo4j"). Caught by actually running the server
    # and reading /health, not by the unit tests (which never round-trip JSON).
    neo4j: ServiceStatus = Field(alias="neo4j")
    graphdb: ServiceStatus
    llm: LlmStatus


@app.get("/health", response_model=HealthResponse, response_model_by_alias=True)
def health() -> HealthResponse:
    # Imported lazily so the module loads even when a backend is down.
    from app.dependencies import get_graphdb, get_llm, get_neo4j

    settings = get_settings()
    neo4j_probe = _probe(lambda: get_neo4j().verify())
    graphdb_probe = _probe(lambda: get_graphdb().verify())
    llm_probe = _probe(lambda: get_llm().verify())
    return HealthResponse(
        status="ok",
        profile=settings.profile,
        ontology_repository=settings.graphdb_repository,
        neo4j=ServiceStatus(**neo4j_probe),
        graphdb=ServiceStatus(**graphdb_probe),
        llm=LlmStatus(model=settings.nvidia_model, **llm_probe),
    )


from api import agent as agent_routes  # noqa: E402
from api import chat as chat_routes  # noqa: E402
from api import enrich as enrich_routes  # noqa: E402
from api import graph as graph_routes  # noqa: E402
from api import graphs as graphs_routes  # noqa: E402
from api import history as history_routes  # noqa: E402
from api import ingest as ingest_routes  # noqa: E402
from api import memory as memory_routes  # noqa: E402
from api import ontology as ontology_routes  # noqa: E402
from api import query as query_routes  # noqa: E402
from api import reason as reason_routes  # noqa: E402
from api import rules as rules_routes  # noqa: E402
from api import settings as settings_routes  # noqa: E402
from api import skills as skills_routes  # noqa: E402

app.include_router(ingest_routes.router)
app.include_router(graph_routes.router)
app.include_router(graphs_routes.router)
app.include_router(history_routes.router)
app.include_router(reason_routes.router)
app.include_router(query_routes.router)
app.include_router(rules_routes.router)
app.include_router(chat_routes.router)
app.include_router(ontology_routes.router)
app.include_router(enrich_routes.router)
app.include_router(agent_routes.router)
app.include_router(skills_routes.router)
app.include_router(memory_routes.router)
app.include_router(settings_routes.router)
