"""Integration tests for services/memory_config_service.py -- the
runtime-mutable store backing the Connection Center's Memory Backend tab
(GRAPHITI_INTEGRATION_PLAN.md §4). Isolated from services/preferences_store.py
on purpose: that store has a public GET /memory/preferences listing endpoint,
and this config holds real secrets (a Graphiti Neo4j password, an optional
embedding API key override) that must never be exposed through it.
"""

from __future__ import annotations

import pytest

from app.config import get_settings
from db.neo4j_client import Neo4jClient
from services import memory_config_service


@pytest.fixture
def neo4j():
    client = Neo4jClient(get_settings())
    try:
        client.verify()
    except Exception:
        pytest.skip("Neo4j not reachable")
    yield client
    client.run("MATCH (c:MemoryBackendConfig {id: 'singleton'}) DETACH DELETE c")
    client.close()


def test_default_backend_is_native_when_unset(neo4j):
    assert memory_config_service.get_backend(neo4j) == "native"


def test_set_and_get_backend(neo4j):
    memory_config_service.set_backend(neo4j, "graphiti")
    assert memory_config_service.get_backend(neo4j) == "graphiti"


def test_set_backend_rejects_unknown_value(neo4j):
    with pytest.raises(ValueError):
        memory_config_service.set_backend(neo4j, "not-a-real-backend")


def test_save_and_get_graphiti_connection(neo4j):
    memory_config_service.save_graphiti_connection(
        neo4j, uri="bolt://localhost:7687", user="neo4j", password="s3cr3t", database="graphiti_memory",
    )
    conn = memory_config_service.get_graphiti_connection(neo4j)
    assert conn is not None
    assert conn.uri == "bolt://localhost:7687"
    assert conn.user == "neo4j"
    assert conn.password == "s3cr3t"
    assert conn.database == "graphiti_memory"


def test_get_graphiti_connection_returns_none_when_unset(neo4j):
    assert memory_config_service.get_graphiti_connection(neo4j) is None


def test_save_and_get_embedding_override(neo4j):
    memory_config_service.save_embedding_override(
        neo4j, base_url="https://example.com/v1", model="custom/embed-model", api_key="key123",
    )
    override = memory_config_service.get_embedding_override(neo4j)
    assert override is not None
    assert override.base_url == "https://example.com/v1"
    assert override.model == "custom/embed-model"
    assert override.api_key == "key123"


def test_status_never_includes_secrets(neo4j):
    memory_config_service.save_graphiti_connection(
        neo4j, uri="bolt://localhost:7687", user="neo4j", password="s3cr3t", database="graphiti_memory",
    )
    memory_config_service.save_embedding_override(
        neo4j, base_url="https://example.com/v1", model="custom/embed-model", api_key="key123",
    )

    status = memory_config_service.get_status(neo4j)

    status_text = str(status)
    assert "s3cr3t" not in status_text
    assert "key123" not in status_text
    assert status.graphiti_configured is True
    assert status.graphiti_neo4j_uri == "bolt://localhost:7687"
    assert status.graphiti_neo4j_database == "graphiti_memory"
    assert status.embedding_configured is True
    assert status.embedding_base_url == "https://example.com/v1"
    assert status.embedding_model == "custom/embed-model"


def test_status_reports_unconfigured_when_nothing_saved(neo4j):
    status = memory_config_service.get_status(neo4j)
    assert status.graphiti_configured is False
    assert status.embedding_configured is False
