"""API tests for POST /graph-maintenance/{graph_id}/run and
GET /graph-maintenance/{graph_id}/runs (2026-07-13 plan §12.3, Feature 7)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from db.neo4j_client import Neo4jClient
from services import graph_service


@pytest.fixture
def client_and_neo4j():
    settings = get_settings()
    neo4j = Neo4jClient(settings)
    try:
        neo4j.verify()
    except Exception:
        pytest.skip("Neo4j not reachable")

    from app.main import app

    graph_id = f"test-{uuid.uuid4().hex[:8]}"
    with TestClient(app) as test_client:
        yield test_client, neo4j, graph_id

    neo4j.run("MATCH (e:Entity {graphId: $gid}) DETACH DELETE e", gid=graph_id)
    neo4j.run("MATCH (f:DerivedFact {graphId: $gid}) DETACH DELETE f", gid=graph_id)
    neo4j.run("MATCH (l:LoopRun {graphId: $gid}) DETACH DELETE l", gid=graph_id)
    neo4j.run("MATCH (s:MaintenanceSchedule {graphId: $gid}) DETACH DELETE s", gid=graph_id)
    neo4j.close()


def test_run_maintenance_on_an_empty_graph_returns_a_real_summary(client_and_neo4j):
    client, _neo4j, graph_id = client_and_neo4j

    resp = client.post(f"/graph-maintenance/{graph_id}/run")

    assert resp.status_code == 200
    body = resp.json()
    assert body["graphId"] == graph_id
    assert body["reasoningRan"] is False
    assert body["minedCandidateIds"] == []
    assert "reasoning skipped" in body["summaryText"]


def test_run_maintenance_is_persisted_and_listable(client_and_neo4j):
    client, neo4j, graph_id = client_and_neo4j
    graph_service.upsert_entity(neo4j, graph_id=graph_id, entity_id="a", label="A", type_="organization", source_doc="d", extraction_confidence=1.0)

    run_resp = client.post(f"/graph-maintenance/{graph_id}/run")
    assert run_resp.status_code == 200
    run_id = run_resp.json()["id"]

    list_resp = client.get(f"/graph-maintenance/{graph_id}/runs")
    assert list_resp.status_code == 200
    assert any(r["id"] == run_id for r in list_resp.json()["runs"])


def test_get_schedule_defaults_to_disabled(client_and_neo4j):
    client, _neo4j, graph_id = client_and_neo4j

    resp = client.get(f"/graph-maintenance/{graph_id}/schedule")

    assert resp.status_code == 200
    assert resp.json()["enabled"] is False


def test_set_schedule_enables_and_live_updates_the_scheduler(client_and_neo4j):
    client, _neo4j, graph_id = client_and_neo4j
    from services import maintenance_scheduler

    resp = client.post(f"/graph-maintenance/{graph_id}/schedule", json={"enabled": True, "intervalMinutes": 30})

    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is True
    assert body["intervalMinutes"] == 30
    # The live scheduler picked this up immediately, not just persisted.
    job = maintenance_scheduler.scheduler.get_job(maintenance_scheduler._job_id(graph_id))
    assert job is not None
    maintenance_scheduler.sync_job(graph_id, enabled=False, interval_minutes=30)  # cleanup


def test_set_schedule_rejects_an_interval_below_the_safety_floor(client_and_neo4j):
    client, _neo4j, graph_id = client_and_neo4j

    resp = client.post(f"/graph-maintenance/{graph_id}/schedule", json={"enabled": True, "intervalMinutes": 1})

    assert resp.status_code == 400
