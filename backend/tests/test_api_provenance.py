"""API-level tests for provenance + bi-temporal fields (PLAN.md §20, UI_PLAN.md §9.1/9.2)."""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient


class FakeLLM:
    def __init__(self, response: str) -> None:
        self._response = response

    def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        return self._response


@pytest.fixture
def client_and_graph():
    settings = get_settings()
    neo4j = Neo4jClient(settings)
    graphdb = GraphDBClient(settings)
    try:
        neo4j.verify()
        graphdb.verify()
    except Exception:
        pytest.skip("Neo4j/GraphDB not reachable")

    from app.main import app
    from app.dependencies import get_llm

    graph_id = f"test-{uuid.uuid4().hex[:8]}"
    payload = json.dumps({
        "entities": [
            {"name": "Acme Corp", "type": "organization", "confidence": 0.9},
            {"name": "Zurich", "type": "jurisdiction", "confidence": 0.9},
        ],
        "relationships": [
            {"source": "Acme Corp", "relation": "is domiciled in", "target": "Zurich", "confidence": 0.8},
        ],
    })
    app.dependency_overrides[get_llm] = lambda: FakeLLM(payload)

    with TestClient(app) as test_client:
        yield test_client, graph_id

    app.dependency_overrides.clear()
    neo4j.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)
    neo4j.run("MATCH (h:IngestEvent {graphId: $gid}) DETACH DELETE h", gid=graph_id)
    neo4j.close()
    graphdb.close()


def test_node_provenance_lists_ingest_events(client_and_graph):
    client, graph_id = client_and_graph
    client.post("/ingest", json={"graphId": graph_id, "source": {"type": "text", "text": "Acme Corp is domiciled in Zurich."}})

    graph = client.get(f"/graph/{graph_id}").json()
    acme = next(n for n in graph["nodes"] if n["label"] == "Acme Corp")

    resp = client.get(f"/graph/{graph_id}/nodes/{acme['id']}/provenance")

    assert resp.status_code == 200
    events = resp.json()["events"]
    assert len(events) == 1
    assert events[0]["text"] == "Acme Corp is domiciled in Zurich."


def test_node_provenance_empty_for_unknown_node(client_and_graph):
    client, graph_id = client_and_graph
    resp = client.get(f"/graph/{graph_id}/nodes/no-such-node/provenance")
    assert resp.status_code == 200
    assert resp.json()["events"] == []


def test_ingest_response_edges_carry_bi_temporal_fields(client_and_graph):
    """The /ingest response itself (not just a later /graph fetch) must carry
    the new fields -- caught live: api/ingest.py has its own separate
    EdgeResponse, not the one in api/graph.py."""
    client, graph_id = client_and_graph
    resp = client.post("/ingest", json={"graphId": graph_id, "source": {"type": "text", "text": "Acme Corp is domiciled in Zurich."}})

    assert resp.status_code == 200
    edge = resp.json()["edges"][0]
    assert edge["validAt"] is not None
    assert edge["invalidAt"] is None
    assert edge["producedByEventId"] is not None


def test_ingest_and_graph_responses_carry_entity_summary(client_and_graph):
    client, graph_id = client_and_graph
    resp = client.post("/ingest", json={"graphId": graph_id, "source": {"type": "text", "text": "Acme Corp is domiciled in Zurich."}})
    assert resp.status_code == 200
    acme = next(n for n in resp.json()["nodes"] if n["label"] == "Acme Corp")
    assert acme["summary"] != ""

    graph = client.get(f"/graph/{graph_id}").json()
    acme_from_graph = next(n for n in graph["nodes"] if n["label"] == "Acme Corp")
    assert acme_from_graph["summary"] != ""


def test_relationship_history_endpoint_returns_current_and_invalidated(client_and_graph):
    """UI_PLAN.md §9.2.2/9.2.3: the full history endpoint, not just current-state /graph."""
    client, graph_id = client_and_graph
    client.post("/ingest", json={"graphId": graph_id, "source": {"type": "text", "text": "Acme Corp is domiciled in Zurich."}})

    from services import graph_service
    from app.config import get_settings
    from db.neo4j_client import Neo4jClient

    neo4j = Neo4jClient(get_settings())
    graph = graph_service.get_graph(neo4j, graph_id)
    acme = next(n for n in graph.nodes if n.label == "Acme Corp")
    geneva_id = f"{graph_id}:geneva"
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id=geneva_id, label="Geneva", type_="jurisdiction", source_doc="manual", extraction_confidence=1.0)
    graph_service.upsert_relationship(
        neo4j, graph_id=graph_id, edge_id=f"{graph_id}:r-geneva", source_id=acme.id, target_id=geneva_id,
        type_="is domiciled in", weight=1.0,
    )
    neo4j.close()

    resp = client.get(f"/graph/{graph_id}/relationships/history", params={"sourceId": acme.id, "type": "is domiciled in"})

    assert resp.status_code == 200
    edges = resp.json()["edges"]
    assert len(edges) == 2
    by_target = {e["target"]: e for e in edges}
    assert by_target[geneva_id]["invalidAt"] is None
    zurich_edge = next(e for e in edges if e["target"] != geneva_id)
    assert zurich_edge["invalidAt"] is not None


def test_edge_response_carries_bi_temporal_fields(client_and_graph):
    client, graph_id = client_and_graph
    client.post("/ingest", json={"graphId": graph_id, "source": {"type": "text", "text": "Acme Corp is domiciled in Zurich."}})

    graph = client.get(f"/graph/{graph_id}").json()

    assert len(graph["edges"]) == 1
    edge = graph["edges"][0]
    assert edge["validAt"] is not None
    assert edge["invalidAt"] is None
    assert edge["producedByEventId"] is not None
