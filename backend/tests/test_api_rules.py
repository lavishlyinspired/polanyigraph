from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_get_rules_returns_real_fibo_seed_rules():
    with TestClient(app) as client:
        resp = client.get("/rules")
    assert resp.status_code == 200
    body = resp.json()
    seed_rules = [r for r in body["rules"] if r["source"] == "seed"]
    assert len(seed_rules) == 4
    edge_types = {r["edgeType"] for r in seed_rules}
    assert "issues" in edge_types
