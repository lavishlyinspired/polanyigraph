"""Regression test: /health JSON keys must match frontend/src/lib/api.ts exactly.

Added after `neo4j` was silently mangled to `neo4J` by pydantic's alias_generator
(digit->letter boundary treated as a word split) — caught only by actually
running the server, not by any prior unit test.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_json_keys_match_frontend_contract():
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "neo4j" in body, f"expected 'neo4j' key, got: {list(body.keys())}"
    assert "graphdb" in body
    assert "llm" in body
    assert "ontologyRepository" in body
