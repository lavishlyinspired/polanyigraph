"""API-level test for GET /ontology (real class/property labels for the
Construct tab's Add Node / Add Edge / Rules Manager pickers)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from db.graphdb_client import GraphDBClient
from app.main import app


def test_get_ontology_returns_real_vocabulary():
    client = GraphDBClient(get_settings())
    try:
        client.verify()
    except Exception:
        pytest.skip("GraphDB not reachable")
    finally:
        client.close()

    with TestClient(app) as test_client:
        resp = test_client.get("/ontology")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["classLabels"]) > 0
    assert len(body["propertyLabels"]) > 0
    assert "organization" in {c.lower() for c in body["classLabels"]}
