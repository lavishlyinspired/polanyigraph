"""GET /settings/connections -- real, non-secret connection info for the
frontend's Connection Center. No passwords/API keys are ever included."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


def test_connections_returns_real_non_secret_config():
    settings = get_settings()
    with TestClient(app) as client:
        resp = client.get("/settings/connections")

    assert resp.status_code == 200
    body = resp.json()

    assert body["profile"] == settings.profile
    assert body["neo4j"]["uri"] == settings.neo4j_uri
    assert body["neo4j"]["database"] == settings.neo4j_database
    assert body["graphdb"]["baseUrl"] == settings.graphdb_base_url
    assert body["graphdb"]["repository"] == settings.graphdb_repository
    assert body["llm"]["baseUrl"] == settings.llm_base_url
    assert body["llm"]["model"] == settings.nvidia_model
    assert body["reasoning"]["decay"] == settings.reason_decay
    assert body["reasoning"]["maxIterations"] == settings.reason_max_iterations


def test_connections_never_leaks_secrets():
    with TestClient(app) as client:
        resp = client.get("/settings/connections")
    body_text = resp.text
    settings = get_settings()

    if settings.neo4j_password:
        assert settings.neo4j_password not in body_text
    if settings.nvidia_api_key:
        assert settings.nvidia_api_key not in body_text


def test_connections_reports_provisioned_but_unwired_services_by_name_only():
    """.env can carry real credentials (Auth0, Qdrant, ...) for services no
    code path reads. Surface that honestly -- service names only, never the
    credential values -- instead of silently hiding it."""
    from app.config import Settings

    custom = Settings(
        auth0_client_id="real-client-id",
        auth0_client_secret="real-secret",
        qdrant_cluster_endpoint="https://example.qdrant.io",
        hf_token="",
        zep_api_key="",
        falkor_db_host="",
    )
    app.dependency_overrides[get_settings] = lambda: custom
    try:
        with TestClient(app) as client:
            resp = client.get("/settings/connections")
    finally:
        app.dependency_overrides.clear()

    body = resp.json()
    assert "auth0" in body["provisionedNotWired"]
    assert "qdrant" in body["provisionedNotWired"]
    assert "zep" not in body["provisionedNotWired"]
    assert "falkordb" not in body["provisionedNotWired"]
    assert "real-secret" not in resp.text
    assert "real-client-id" not in resp.text
