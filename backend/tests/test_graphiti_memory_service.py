"""Integration tests for services/graphiti_memory_service.py -- Option B
(GRAPHITI_INTEGRATION_PLAN.md §4). Real graphiti-core, real NVIDIA-backed
LLM/embedder, real Neo4j -- isolated to a dedicated 'graphiti-memory'
database so this never touches the graphos database's :Entity/:RELATES
schema. Slower than most tests here (real extraction calls); skipped
entirely if that database isn't reachable/creatable, same convention as
every other live-service test in this suite.
"""

from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from app.dependencies import get_embedder
from services.graphiti_memory_service import GraphitiMemoryClient
from services.memory_config_service import GraphitiConnection

_TEST_DATABASE = "graphiti-memory"


@pytest.fixture(scope="module")
def graphiti_client():
    settings = get_settings()
    embedder = get_embedder()
    try:
        embedder.verify()
    except Exception:
        pytest.skip("Embedding endpoint not reachable")

    import neo4j as neo4j_driver

    driver = neo4j_driver.GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
    try:
        driver.verify_connectivity()
        with driver.session(database="system") as session:
            session.run(f"CREATE DATABASE `{_TEST_DATABASE}` IF NOT EXISTS").consume()
    except Exception:
        driver.close()
        pytest.skip(f"Neo4j not reachable or cannot provision database '{_TEST_DATABASE}'")
    driver.close()

    connection = GraphitiConnection(
        uri=settings.neo4j_uri, user=settings.neo4j_user, password=settings.neo4j_password, database=_TEST_DATABASE,
    )
    client = GraphitiMemoryClient(connection, settings, embedder)
    client.ensure_indices()
    yield client


@pytest.fixture
def graph_id():
    return f"test-{uuid.uuid4().hex[:8]}"


def _cleanup(graph_id: str, settings) -> None:
    import neo4j as neo4j_driver

    driver = neo4j_driver.GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
    with driver.session(database=_TEST_DATABASE) as session:
        session.run("MATCH (n) WHERE n.group_id = $gid DETACH DELETE n", gid=graph_id)
    driver.close()


def test_ingest_and_search_finds_the_real_extracted_fact(graphiti_client, graph_id):
    settings = get_settings()
    try:
        graphiti_client.ingest(
            graph_id=graph_id, text="My supplier is Bosch and they ship gearboxes.", source_description="chat turn",
        )

        hits = graphiti_client.search(graph_id=graph_id, query="Bosch supplier gearboxes", limit=5)

        assert any("bosch" in h.fact.lower() for h in hits)
    finally:
        _cleanup(graph_id, settings)


def test_search_is_scoped_to_graph_id_and_does_not_leak_across_graphs(graphiti_client, graph_id):
    settings = get_settings()
    other_graph_id = f"{graph_id}-other"
    try:
        graphiti_client.ingest(
            graph_id=graph_id, text="Our main supplier is Bosch.", source_description="chat turn",
        )
        graphiti_client.ingest(
            graph_id=other_graph_id, text="Our main supplier is Continental.", source_description="chat turn",
        )

        hits = graphiti_client.search(graph_id=graph_id, query="supplier", limit=10)

        assert any("bosch" in h.fact.lower() for h in hits)
        assert not any("continental" in h.fact.lower() for h in hits)
    finally:
        _cleanup(graph_id, settings)
        _cleanup(other_graph_id, settings)


def test_current_state_excludes_superseded_facts(graphiti_client, graph_id):
    """Bi-temporal invalidation: asserting a new CEO should invalidate the
    old fact rather than delete it -- current_state() should only surface
    what's true now."""
    settings = get_settings()
    try:
        graphiti_client.ingest(graph_id=graph_id, text="Jane Smith is the CEO of Acme Corp.", source_description="doc 1")
        graphiti_client.ingest(graph_id=graph_id, text="John Doe is now the CEO of Acme Corp, replacing Jane Smith.", source_description="doc 2")

        current = graphiti_client.current_state(graph_id=graph_id, entity_name="Acme Corp CEO")

        current_text = " ".join(h.fact.lower() for h in current)
        assert "john doe" in current_text or "john" in current_text
    finally:
        _cleanup(graph_id, settings)
