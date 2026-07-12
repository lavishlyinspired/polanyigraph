"""Option B: graphiti-core wrapper (GRAPHITI_INTEGRATION_PLAN.md §4).

Bridges this project's synchronous service-layer convention to graphiti-core's
fully-async API. All calls for a given Graphiti client run on one persistent
background event loop (_BackgroundLoop below), not a fresh asyncio.run() per
call -- confirmed live that the latter breaks: the async Neo4j driver's
connection pool is bound to whichever loop was running when it was created,
and a second asyncio.run() (a new loop each time) raises "Future attached to
a different loop" the moment a second call reuses the same Graphiti/driver
instance.

Isolated to its own Neo4j database (never the graphos database's
:Entity/:RELATES schema -- see GRAPHITI_INTEGRATION_PLAN.md §3.1 on the label
collision this avoids), selected via Neo4jDriver(database=...) directly (the
corrected mechanism -- graphiti_core.Graphiti has no database= kwarg of its
own; group_id is a same-database partition, not a database selector).

CONFIRMED LIVE BUG in graphiti-core 0.29.2's Neo4jDriver.execute_query()
(graphiti_core/driver/neo4j_driver.py): it sets `database_` inside the
`params` dict passed as `parameters_=params` to the underlying neo4j driver's
execute_query(), instead of passing `database_=self._database` as its own
top-level kwarg (which is what the neo4j driver actually reads for routing --
verified against neo4j.AsyncDriver.execute_query's real signature). Since no
Graphiti Cypher query declares a `$database_` parameter, the value is just
silently discarded and the driver's built-in default ('neo4j') is used
instead -- meaning build_indices_and_constraints() and search() silently ran
against the wrong database. Confirmed live: writes via driver.session()
(add_episode's path) correctly used the configured database; index creation
and search via execute_query() did not, leaving 31 stray index definitions on
this project's *primary* Neo4j database (no data was written there --
session()-based writes were unaffected -- but cleanup was required; see git
history). _RoutedNeo4jDriver below overrides execute_query() to pass
database_ correctly.

Telemetry disabled unconditionally (GRAPHITI_TELEMETRY_ENABLED=false) before
importing graphiti_core -- this project processes real document content and
shouldn't phone home to PostHog by default.
"""

from __future__ import annotations

import asyncio
import os
import threading
from collections.abc import Coroutine
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypeVar

os.environ.setdefault("GRAPHITI_TELEMETRY_ENABLED", "false")

from graphiti_core import Graphiti  # noqa: E402
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient  # noqa: E402
from graphiti_core.driver.neo4j_driver import Neo4jDriver  # noqa: E402
from graphiti_core.embedder.client import EmbedderClient  # noqa: E402
from graphiti_core.llm_client.config import LLMConfig  # noqa: E402
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient  # noqa: E402
from graphiti_core.nodes import EpisodeType  # noqa: E402

from app.config import Settings  # noqa: E402
from llm.embedder import EmbeddingClient  # noqa: E402
from services.memory_config_service import GraphitiConnection  # noqa: E402

T = TypeVar("T")


class _BackgroundLoop:
    """A single persistent event loop in its own daemon thread. Every
    coroutine for a given Graphiti client is dispatched here via
    run_coroutine_threadsafe so loop-bound async resources (the Neo4j async
    driver's connection pool) are always used from the loop they were
    created on."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run(self, coro: Coroutine[Any, Any, T]) -> T:
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()


class _RoutedNeo4jDriver(Neo4jDriver):
    """Fixes execute_query() ignoring the configured database -- see module
    docstring. Only execute_query needed overriding; session() already routes
    correctly (it reads self._database directly, not through parameters_)."""

    async def execute_query(self, cypher_query_, **kwargs):
        params = kwargs.pop("params", None) or {}
        params.pop("database_", None)  # drop the mis-placed value graphiti-core sets
        return await self.client.execute_query(
            cypher_query_, parameters_=params, database_=self._database, **kwargs
        )


class _EmbedderAdapter(EmbedderClient):
    """Bridges llm.embedder.EmbeddingClient (sync, input_type-aware) to
    graphiti's async EmbedderClient interface. Needed because this project's
    default embedding model (nvidia/nv-embedqa-e5-v5) is asymmetric and
    rejects requests with no input_type -- graphiti's own OpenAIEmbedder
    never sends one."""

    def __init__(self, client: EmbeddingClient) -> None:
        self._client = client

    async def create(self, input_data) -> list[float]:
        text = input_data if isinstance(input_data, str) else " ".join(str(x) for x in input_data)
        vectors = await asyncio.to_thread(self._client.embed, [text], input_type="passage")
        return vectors[0]

    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self._client.embed, input_data_list, input_type="passage")


@dataclass(frozen=True)
class GraphitiMemoryHit:
    id: str
    fact: str
    valid_at: str | None
    invalid_at: str | None


class GraphitiMemoryClient:
    """Owns one Graphiti instance plus the background loop it must always
    run on. Construct once per (connection, settings, embedder) triple and
    reuse -- rebuilding per call would work but throws away the Neo4j
    connection pool every time."""

    def __init__(self, connection: GraphitiConnection, settings: Settings, embedding_client: EmbeddingClient) -> None:
        self._loop = _BackgroundLoop()
        self._graphiti = self._loop.run(self._build(connection, settings, embedding_client))

    @staticmethod
    async def _build(connection: GraphitiConnection, settings: Settings, embedding_client: EmbeddingClient) -> Graphiti:
        driver = _RoutedNeo4jDriver(connection.uri, connection.user, connection.password, database=connection.database)
        llm_config = LLMConfig(api_key=settings.nvidia_api_key, model=settings.nvidia_model, base_url=settings.llm_base_url)
        return Graphiti(
            graph_driver=driver,
            # Graphiti's default OpenAIClient calls OpenAI's newer /responses API
            # for structured output, which NVIDIA's NIM endpoint (chat/completions
            # only) 404s on -- confirmed live. OpenAIGenericClient targets plain
            # /chat/completions with json_schema structured output instead, which
            # NVIDIA's endpoint does support (also confirmed live).
            llm_client=OpenAIGenericClient(config=llm_config),
            embedder=_EmbedderAdapter(embedding_client),
            # Graphiti defaults cross_encoder to a bare OpenAIRerankerClient(),
            # which requires OPENAI_API_KEY in the environment -- this project
            # never sets that (it uses NVIDIA_API_KEY instead), so it needs an
            # explicit config pointed at the same endpoint or construction fails.
            cross_encoder=OpenAIRerankerClient(config=llm_config),
        )

    def ensure_indices(self) -> None:
        self._loop.run(self._graphiti.build_indices_and_constraints())

    def ingest(self, *, graph_id: str, text: str, source_description: str) -> None:
        """One real episode per ingest call, partitioned by group_id=graph_id
        so multiple graphs sharing one Graphiti database don't bleed into
        each other's facts -- same graph_id scoping convention as every
        :Entity/:RELATES node in the native store."""
        self._loop.run(
            self._graphiti.add_episode(
                name=f"{graph_id}-{datetime.now(UTC).isoformat()}",
                episode_body=text,
                source=EpisodeType.text,
                source_description=source_description,
                reference_time=datetime.now(UTC),
                group_id=graph_id,
            )
        )

    def search(self, *, graph_id: str, query: str, limit: int = 10) -> list[GraphitiMemoryHit]:
        edges = self._loop.run(self._graphiti.search(query, group_ids=[graph_id], num_results=limit))
        return [
            GraphitiMemoryHit(
                id=edge.uuid,
                fact=edge.fact,
                valid_at=edge.valid_at.isoformat() if edge.valid_at else None,
                invalid_at=edge.invalid_at.isoformat() if edge.invalid_at else None,
            )
            for edge in edges
        ]

    def timeline(self, *, graph_id: str, entity_name: str) -> list[GraphitiMemoryHit]:
        """All facts (current and superseded) mentioning entity_name, oldest
        first -- Graphiti's bi-temporal edges make "what was true, and when"
        a real query instead of losing history to an overwrite, same
        motivation as the native store's get_relationship_history()."""
        hits = self.search(graph_id=graph_id, query=entity_name, limit=50)
        return sorted(hits, key=lambda h: h.valid_at or "")

    def current_state(self, *, graph_id: str, entity_name: str) -> list[GraphitiMemoryHit]:
        """Only facts still valid now (invalid_at is None) -- superseded ones
        stay queryable via timeline() but don't show up here."""
        return [hit for hit in self.timeline(graph_id=graph_id, entity_name=entity_name) if hit.invalid_at is None]


_client_cache: dict[tuple[str, str, str, str], GraphitiMemoryClient] = {}


def get_or_build_client(connection: GraphitiConnection, settings: Settings, embedding_client: EmbeddingClient) -> GraphitiMemoryClient:
    """Reuses one GraphitiMemoryClient (and its background loop + Neo4j
    connection pool) per distinct connection, instead of rebuilding one on
    every call -- construction spins up a real driver and a thread."""
    key = (connection.uri, connection.user, connection.password, connection.database)
    if key not in _client_cache:
        _client_cache[key] = GraphitiMemoryClient(connection, settings, embedding_client)
    return _client_cache[key]
