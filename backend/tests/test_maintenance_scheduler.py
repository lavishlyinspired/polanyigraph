"""Tests for services/maintenance_scheduler.py -- the live APScheduler
wrapper around Feature 7's maintenance loop. Real Neo4j (no mocks) for the
config-resync test; the module-level `scheduler` singleton is real too
(APScheduler itself, not faked), scoped carefully per test via unique
graph_ids and explicit cleanup so tests don't interfere with each other.
"""

from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from db.neo4j_client import Neo4jClient
from services import maintenance_schedule_service, maintenance_scheduler


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
    job_id = maintenance_scheduler._job_id(graph_id)
    if maintenance_scheduler.scheduler.get_job(job_id) is not None:
        maintenance_scheduler.scheduler.remove_job(job_id)
    client.close()


def test_sync_job_adds_a_job_when_enabled(neo4j):
    _client, graph_id = neo4j

    maintenance_scheduler.sync_job(graph_id, enabled=True, interval_minutes=30)

    job = maintenance_scheduler.scheduler.get_job(maintenance_scheduler._job_id(graph_id))
    assert job is not None
    assert job.trigger.interval.total_seconds() == 30 * 60


def test_sync_job_removes_a_job_when_disabled(neo4j):
    _client, graph_id = neo4j
    maintenance_scheduler.sync_job(graph_id, enabled=True, interval_minutes=30)

    maintenance_scheduler.sync_job(graph_id, enabled=False, interval_minutes=30)

    assert maintenance_scheduler.scheduler.get_job(maintenance_scheduler._job_id(graph_id)) is None


def test_sync_job_disabling_an_already_absent_job_does_not_raise(neo4j):
    _client, graph_id = neo4j
    maintenance_scheduler.sync_job(graph_id, enabled=False, interval_minutes=30)  # never added -- must not raise


def test_sync_job_replaces_an_existing_job_with_a_new_interval(neo4j):
    _client, graph_id = neo4j
    maintenance_scheduler.sync_job(graph_id, enabled=True, interval_minutes=30)

    maintenance_scheduler.sync_job(graph_id, enabled=True, interval_minutes=90)

    job = maintenance_scheduler.scheduler.get_job(maintenance_scheduler._job_id(graph_id))
    assert job.trigger.interval.total_seconds() == 90 * 60


@pytest.mark.asyncio
async def test_start_resyncs_every_enabled_schedule_from_neo4j(neo4j):
    client, graph_id = neo4j
    maintenance_schedule_service.set_schedule(client, graph_id, enabled=True, interval_minutes=45)

    try:
        maintenance_scheduler.start(client)
        job = maintenance_scheduler.scheduler.get_job(maintenance_scheduler._job_id(graph_id))
        assert job is not None
        assert job.trigger.interval.total_seconds() == 45 * 60
    finally:
        maintenance_scheduler.shutdown()
