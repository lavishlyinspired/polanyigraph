"""Tests for services/maintenance_schedule_service.py -- per-graph
configuration for Feature 7's autonomous maintenance loop. Real Neo4j, no
mocks, per project convention."""

from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from db.neo4j_client import Neo4jClient
from services import maintenance_schedule_service


@pytest.fixture
def neo4j():
    client = Neo4jClient(get_settings())
    try:
        client.verify()
    except Exception:
        pytest.skip("Neo4j not reachable")
    graph_id = f"test-{uuid.uuid4().hex[:8]}"
    yield client, graph_id
    client.run("MATCH (s:MaintenanceSchedule {graphId: $gid}) DETACH DELETE s", gid=graph_id)
    client.close()


def test_get_schedule_defaults_to_disabled_for_an_unconfigured_graph(neo4j):
    client, graph_id = neo4j

    schedule = maintenance_schedule_service.get_schedule(client, graph_id)

    assert schedule.enabled is False


def test_set_schedule_persists_enabled_and_interval(neo4j):
    client, graph_id = neo4j

    result = maintenance_schedule_service.set_schedule(client, graph_id, enabled=True, interval_minutes=30)

    assert result.enabled is True
    assert result.interval_minutes == 30
    fetched = maintenance_schedule_service.get_schedule(client, graph_id)
    assert fetched.enabled is True
    assert fetched.interval_minutes == 30


def test_set_schedule_rejects_an_interval_below_the_safety_floor(neo4j):
    client, graph_id = neo4j

    with pytest.raises(ValueError):
        maintenance_schedule_service.set_schedule(client, graph_id, enabled=True, interval_minutes=1)


def test_set_schedule_can_disable_an_enabled_schedule(neo4j):
    client, graph_id = neo4j
    maintenance_schedule_service.set_schedule(client, graph_id, enabled=True, interval_minutes=30)

    result = maintenance_schedule_service.set_schedule(client, graph_id, enabled=False, interval_minutes=30)

    assert result.enabled is False


def test_record_run_sets_last_run_at(neo4j):
    client, graph_id = neo4j
    maintenance_schedule_service.set_schedule(client, graph_id, enabled=True, interval_minutes=30)
    assert maintenance_schedule_service.get_schedule(client, graph_id).last_run_at is None

    maintenance_schedule_service.record_run(client, graph_id)

    assert maintenance_schedule_service.get_schedule(client, graph_id).last_run_at is not None


def test_list_enabled_schedules_only_returns_enabled_ones(neo4j):
    client, graph_id = neo4j
    other_graph_id = f"{graph_id}-other"
    maintenance_schedule_service.set_schedule(client, graph_id, enabled=True, interval_minutes=30)
    maintenance_schedule_service.set_schedule(client, other_graph_id, enabled=False, interval_minutes=30)

    try:
        enabled = maintenance_schedule_service.list_enabled_schedules(client)
        assert graph_id in {s.graph_id for s in enabled}
        assert other_graph_id not in {s.graph_id for s in enabled}
    finally:
        client.run("MATCH (s:MaintenanceSchedule {graphId: $gid}) DETACH DELETE s", gid=other_graph_id)
