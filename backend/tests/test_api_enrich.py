"""API-level tests for POST /enrich/{graphId} and pending-fact approve/reject
(PLAN.md §19.6 step 3, §7.3 human-in-the-loop)."""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient


class FakeLLM:
    """Extraction and enrichment both go through complete_json, so this fakes
    both: the extraction payload for entities/relationships, and a fixed
    causal-relation fact for anything that looks like an enrichment prompt."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        self.calls.append(user)
        if "Causal Relations" in system or "causal" in system.lower():
            return json.dumps({
                "facts": [
                    {"text": "The heavy rain caused the match to be postponed.", "anchors": ["__ANCHOR__"], "confidence": 0.9}
                ]
            })
        return json.dumps({
            "entities": [{"name": "the match", "type": "organization", "confidence": 0.9}],
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
    except Exception:
        pytest.skip("Neo4j/GraphDB not reachable")

    from app.dependencies import get_llm
    from app.main import app

    graph_id = f"test-{uuid.uuid4().hex[:8]}"
    llm = FakeLLM()
    app.dependency_overrides[get_llm] = lambda: llm

    with TestClient(app) as test_client:
        yield test_client, graph_id, llm

    app.dependency_overrides.clear()
    neo4j.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)
    neo4j.run("MATCH (f:ImplicitFact {graphId: $gid}) DETACH DELETE f", gid=graph_id)
    neo4j.run("MATCH (h:IngestEvent {graphId: $gid}) DETACH DELETE h", gid=graph_id)
    neo4j.close()
    graphdb.close()


def test_enrich_runs_causal_relations_against_the_real_graph(client_and_graph):
    client, graph_id, llm = client_and_graph
    ingest_resp = client.post("/ingest", json={"graphId": graph_id, "source": {"type": "text", "text": "The heavy rain forced the match to be postponed."}})
    entity_id = ingest_resp.json()["nodes"][0]["id"]
    # The fake LLM doesn't know the real entity id ahead of time; patch its
    # canned anchor to the real one so the anchoring-integrity check passes.
    llm.calls.clear()

    class AnchoringFakeLLM(FakeLLM):
        def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
            if "causal" in system.lower():
                return json.dumps({"facts": [{"text": "The heavy rain caused the match to be postponed.", "anchors": [entity_id], "confidence": 0.9}]})
            return super().complete_json(system=system, user=user, temperature=temperature)

    from app.dependencies import get_llm
    from app.main import app
    app.dependency_overrides[get_llm] = lambda: AnchoringFakeLLM()

    resp = client.post(f"/enrich/{graph_id}", json={"text": "The heavy rain forced the match to be postponed."})

    assert resp.status_code == 200
    facts = resp.json()["facts"]
    assert len(facts) == 1
    assert facts[0]["heuristicType"] == "causal_relation"
    assert facts[0]["status"] == "pending"
    assert facts[0]["anchorEntityIds"] == [entity_id]


def test_pending_and_approve_reject_lifecycle(client_and_graph):
    client, graph_id, llm = client_and_graph
    ingest_resp = client.post("/ingest", json={"graphId": graph_id, "source": {"type": "text", "text": "The heavy rain forced the match to be postponed."}})
    entity_id = ingest_resp.json()["nodes"][0]["id"]

    class AnchoringFakeLLM(FakeLLM):
        def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
            if "causal" in system.lower():
                return json.dumps({"facts": [{"text": "fact", "anchors": [entity_id], "confidence": 0.9}]})
            return super().complete_json(system=system, user=user, temperature=temperature)

    from app.dependencies import get_llm
    from app.main import app
    app.dependency_overrides[get_llm] = lambda: AnchoringFakeLLM()

    enrich_resp = client.post(f"/enrich/{graph_id}", json={"text": "text"})
    fact_id = enrich_resp.json()["facts"][0]["id"]

    pending = client.get(f"/enrich/{graph_id}/pending").json()["facts"]
    assert len(pending) == 1

    approve_resp = client.post(f"/enrich/{graph_id}/{fact_id}/approve")
    assert approve_resp.status_code == 200

    assert client.get(f"/enrich/{graph_id}/pending").json()["facts"] == []
    approved = client.get(f"/enrich/{graph_id}/approved").json()["facts"]
    assert len(approved) == 1
    assert approved[0]["status"] == "approved"


def test_reject_removes_fact_from_pending(client_and_graph):
    client, graph_id, llm = client_and_graph
    ingest_resp = client.post("/ingest", json={"graphId": graph_id, "source": {"type": "text", "text": "The heavy rain forced the match to be postponed."}})
    entity_id = ingest_resp.json()["nodes"][0]["id"]

    class AnchoringFakeLLM(FakeLLM):
        def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
            if "causal" in system.lower():
                return json.dumps({"facts": [{"text": "fact", "anchors": [entity_id], "confidence": 0.9}]})
            return super().complete_json(system=system, user=user, temperature=temperature)

    from app.dependencies import get_llm
    from app.main import app
    app.dependency_overrides[get_llm] = lambda: AnchoringFakeLLM()

    enrich_resp = client.post(f"/enrich/{graph_id}", json={"text": "text"})
    fact_id = enrich_resp.json()["facts"][0]["id"]

    client.post(f"/enrich/{graph_id}/{fact_id}/reject")

    assert client.get(f"/enrich/{graph_id}/pending").json()["facts"] == []
    assert client.get(f"/enrich/{graph_id}/approved").json()["facts"] == []
