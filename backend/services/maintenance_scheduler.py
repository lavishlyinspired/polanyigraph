"""In-process recurring scheduler for Feature 7's graph maintenance loop
(2026-07-13 checklist follow-up: "let it run automatically" + "configure
from the UI"). APScheduler's AsyncIOScheduler -- runs inside this FastAPI
process's own event loop; no external service (Celery/Redis/a real cron
daemon) needed for a single-process desktop app, the same "don't add
infrastructure this deployment doesn't need" reasoning already used for
LangGraph's InMemorySaver checkpointer.

:MaintenanceSchedule (services/maintenance_schedule_service.py) is the
source of truth, survives process restarts; this module's in-memory
AsyncIOScheduler is a live cache of "enabled" schedules, resynced from
Neo4j once at process startup (app/main.py's lifespan) and updated
directly whenever POST /graph-maintenance/{graph_id}/schedule changes a
graph's config, so a schedule change takes effect immediately without
waiting for the next restart.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.dependencies import get_graphdb, get_neo4j, get_settings
from services import graph_maintenance_loop, maintenance_schedule_service

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def _job_id(graph_id: str) -> str:
    return f"graph-maintenance:{graph_id}"


def _run_job(graph_id: str) -> None:
    """The scheduler's own callback -- not triggered by an HTTP request, so
    it builds its own client instances (the same @lru_cache singletons
    every request handler uses) rather than relying on FastAPI's
    Depends()-injected ones."""
    neo4j = get_neo4j()
    try:
        summary = graph_maintenance_loop.run_maintenance_loop(neo4j, get_graphdb(), get_settings(), graph_id)
        maintenance_schedule_service.record_run(neo4j, graph_id)
        logger.info("graph maintenance loop ran for %s: %s", graph_id, summary.as_summary_text())
    except Exception:
        # A scheduled background job that raises would otherwise crash
        # silently or (depending on APScheduler config) stop rescheduling
        # -- log and let the next tick try again, same "don't let one bad
        # run take down recurring infrastructure" posture as everything
        # else in this codebase that degrades rather than crashes.
        logger.exception("graph maintenance loop failed for %s", graph_id)


def sync_job(graph_id: str, *, enabled: bool, interval_minutes: int) -> None:
    """Adds, updates, or removes graph_id's recurring job so the live
    scheduler matches its current persisted config. Called right after
    maintenance_schedule_service.set_schedule persists that config (REST
    endpoint), and once per already-enabled graph at process startup.

    Explicit remove-then-add rather than relying on add_job's own
    replace_existing=True: verified empirically that replace_existing
    silently fails to update an existing job's trigger/interval unless the
    scheduler is already running (a real, non-obvious APScheduler
    footgun) -- this remove-then-add approach works correctly regardless
    of whether the scheduler has been started yet."""
    job_id = _job_id(graph_id)
    if scheduler.get_job(job_id) is not None:
        scheduler.remove_job(job_id)
    if not enabled:
        return
    scheduler.add_job(
        _run_job, "interval", minutes=interval_minutes, id=job_id, args=[graph_id],
        coalesce=True, max_instances=1,
    )


def start(neo4j) -> None:
    """Starts the scheduler and resyncs every currently-enabled schedule
    from Neo4j -- so a process restart doesn't silently lose an active
    schedule (matches the same resync discipline already used for
    ontology constraints / vector indexes at startup)."""
    if not scheduler.running:
        scheduler.start()
    for schedule in maintenance_schedule_service.list_enabled_schedules(neo4j):
        sync_job(schedule.graph_id, enabled=True, interval_minutes=schedule.interval_minutes)


def shutdown() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
