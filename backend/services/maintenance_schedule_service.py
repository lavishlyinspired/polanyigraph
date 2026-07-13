"""Per-graph configuration for Feature 7's autonomous maintenance loop
(2026-07-13 checklist follow-up: "let it run automatically" + "configure
from the UI"). A single :MaintenanceSchedule node per graph_id -- OFF by
default (an unconfigured graph reads as disabled): nothing runs
automatically until a human explicitly enables it, matching this
project's established opt-in-first precedent for anything that spends
real API budget on its own (enable_compound_queries).
"""

from __future__ import annotations

from dataclasses import dataclass

from db.neo4j_client import Neo4jClient

# Floor, not a suggestion: a UI typo ("run every 0 minutes") could
# otherwise hammer the real LLM/embedding APIs in a tight loop.
MIN_INTERVAL_MINUTES = 5


@dataclass(frozen=True)
class MaintenanceSchedule:
    graph_id: str
    enabled: bool
    interval_minutes: int
    last_run_at: str | None = None


def get_schedule(neo4j: Neo4jClient, graph_id: str) -> MaintenanceSchedule:
    rows = neo4j.run(
        """
        MATCH (s:MaintenanceSchedule {graphId: $graph_id})
        RETURN s.enabled AS enabled, s.intervalMinutes AS intervalMinutes, toString(s.lastRunAt) AS lastRunAt
        """,
        graph_id=graph_id,
    )
    if not rows:
        return MaintenanceSchedule(graph_id=graph_id, enabled=False, interval_minutes=60)
    r = rows[0]
    return MaintenanceSchedule(
        graph_id=graph_id, enabled=r["enabled"], interval_minutes=r["intervalMinutes"], last_run_at=r["lastRunAt"],
    )


def set_schedule(neo4j: Neo4jClient, graph_id: str, *, enabled: bool, interval_minutes: int) -> MaintenanceSchedule:
    if interval_minutes < MIN_INTERVAL_MINUTES:
        raise ValueError(f"interval_minutes must be >= {MIN_INTERVAL_MINUTES}.")
    neo4j.run(
        """
        MERGE (s:MaintenanceSchedule {graphId: $graph_id})
        SET s.enabled = $enabled, s.intervalMinutes = $interval_minutes
        """,
        graph_id=graph_id, enabled=enabled, interval_minutes=interval_minutes,
    )
    return get_schedule(neo4j, graph_id)


def record_run(neo4j: Neo4jClient, graph_id: str) -> None:
    neo4j.run(
        "MATCH (s:MaintenanceSchedule {graphId: $graph_id}) SET s.lastRunAt = datetime()",
        graph_id=graph_id,
    )


def list_enabled_schedules(neo4j: Neo4jClient) -> list[MaintenanceSchedule]:
    rows = neo4j.run(
        """
        MATCH (s:MaintenanceSchedule {enabled: true})
        RETURN s.graphId AS graphId, s.enabled AS enabled, s.intervalMinutes AS intervalMinutes, toString(s.lastRunAt) AS lastRunAt
        """,
    )
    return [
        MaintenanceSchedule(graph_id=r["graphId"], enabled=r["enabled"], interval_minutes=r["intervalMinutes"], last_run_at=r["lastRunAt"])
        for r in rows
    ]
