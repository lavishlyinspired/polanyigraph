"""API-level test for POST /ingest with source.type == "edgar" (MVP_PLAN.md
§7's optional convenience source). Real SEC EDGAR fetch, real Neo4j/GraphDB,
faked LLM (per this repo's extraction-test convention)."""

from __future__ import annotations

import json
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient
from services import edgar_service


class FakeLLM:
    def __init__(self, response: str) -> None:
        self._response = response

    def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        return self._response


_PAYLOAD = json.dumps({
    "entities": [{"name": "Apple Inc.", "type": "organization", "confidence": 0.9}],
    "relationships": [],
})


@pytest.fixture
def client_and_graph():
    settings = get_settings()
    neo4j = Neo4jClient(settings)
    graphdb = GraphDBClient(settings)
    try:
        neo4j.verify()
        graphdb.verify()
        httpx.get(edgar_service.TICKERS_URL, headers={"User-Agent": edgar_service.USER_AGENT}, timeout=5.0).raise_for_status()
    except Exception:
        pytest.skip("Neo4j/GraphDB/SEC EDGAR not reachable")

    from app.dependencies import get_llm
    from app.main import app

    graph_id = f"test-{uuid.uuid4().hex[:8]}"
    app.dependency_overrides[get_llm] = lambda: FakeLLM(_PAYLOAD)

    with TestClient(app) as test_client:
        yield test_client, graph_id

    app.dependency_overrides.clear()
    neo4j.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)
    neo4j.run("MATCH (h:IngestEvent {graphId: $gid}) DETACH DELETE h", gid=graph_id)
    neo4j.close()
    graphdb.close()


def test_ingest_from_real_edgar_filing(client_and_graph):
    client, graph_id = client_and_graph

    resp = client.post("/ingest", json={"graphId": graph_id, "source": {"type": "edgar", "ticker": "AAPL", "formType": "10-K"}})

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["nodes"]) == 1
    assert body["nodes"][0]["label"] == "Apple Inc."
    assert body["nodes"][0]["sourceDoc"].startswith("edgar:AAPL:10-K")


def test_ingest_edgar_404s_for_unknown_ticker(client_and_graph):
    client, graph_id = client_and_graph

    resp = client.post("/ingest", json={"graphId": graph_id, "source": {"type": "edgar", "ticker": "NOT-A-REAL-TICKER-XYZ", "formType": "10-K"}})

    assert resp.status_code == 404
