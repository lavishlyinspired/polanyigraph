"""GET/PUT /settings/memory-backend -- runtime memory-backend selection and
connection testing for the Connection Center (GRAPHITI_INTEGRATION_PLAN.md
§4). Never echoes credential values back over the API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from db.neo4j_client import Neo4jClient


def _clean_config():
    neo4j = Neo4jClient(get_settings())
    neo4j.run("MATCH (c:MemoryBackendConfig {id: 'singleton'}) DETACH DELETE c")
    neo4j.close()


def test_get_memory_backend_defaults_to_native():
    _clean_config()
    try:
        with TestClient(app) as client:
            resp = client.get("/settings/memory-backend")
        assert resp.status_code == 200
        body = resp.json()
        assert body["backend"] == "native"
        assert body["graphitiConfigured"] is False
        assert body["embeddingConfigured"] is False
    finally:
        _clean_config()


def test_put_memory_backend_switches_active_backend():
    _clean_config()
    try:
        with TestClient(app) as client:
            put_resp = client.put("/settings/memory-backend", json={"backend": "graphiti"})
            assert put_resp.status_code == 200
            assert put_resp.json()["backend"] == "graphiti"

            get_resp = client.get("/settings/memory-backend")
            assert get_resp.json()["backend"] == "graphiti"
    finally:
        _clean_config()


def test_put_memory_backend_rejects_unknown_backend():
    with TestClient(app) as client:
        resp = client.put("/settings/memory-backend", json={"backend": "not-a-real-backend"})
    assert resp.status_code == 400


def test_put_graphiti_connection_saves_non_secret_fields_and_never_echoes_password():
    # Real credentials against the real server -- a fake password here trips
    # Neo4j's own AuthenticationRateLimit after a couple of bad attempts,
    # which then blocks *other* tests' real connections too (confirmed live).
    settings = get_settings()
    _clean_config()
    try:
        with TestClient(app) as client:
            resp = client.put(
                "/settings/memory-backend/graphiti-connection",
                json={"uri": settings.neo4j_uri, "user": settings.neo4j_user, "password": settings.neo4j_password, "database": "graphiti-memory"},
            )
        assert resp.status_code == 200
        body = resp.json()
        if settings.neo4j_password:
            assert settings.neo4j_password not in resp.text
        assert body["status"]["graphitiConfigured"] is True
        assert body["status"]["graphitiNeo4jUri"] == settings.neo4j_uri
        assert body["status"]["graphitiNeo4jDatabase"] == "graphiti-memory"
        assert body["ok"] is True
    finally:
        _clean_config()


def test_put_embedding_override_saves_non_secret_fields_and_never_echoes_api_key():
    _clean_config()
    try:
        with TestClient(app) as client:
            resp = client.put(
                "/settings/memory-backend/embedding",
                json={"baseUrl": get_settings().llm_base_url, "model": "nvidia/nv-embedqa-e5-v5", "apiKey": "sekret-key-999"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "sekret-key-999" not in resp.text
        assert body["status"]["embeddingConfigured"] is True
        assert body["status"]["embeddingModel"] == "nvidia/nv-embedqa-e5-v5"
        assert "ok" in body
    finally:
        _clean_config()
