"""POST /graph-maintenance/{graph_id}/run — manually trigger one
autonomous graph maintenance pass (2026-07-13 plan §12.3, Feature 7).

POST /graph-maintenance/{graph_id}/schedule — configure REAL, automatic
periodic runs (checklist follow-up: "let it run automatically" + "allow
scheduler configuration from ui"), backed by services/maintenance_scheduler.py
(APScheduler, in-process) and services/maintenance_schedule_service.py
(persisted config, survives restarts). OFF by default per graph_id --
nothing runs on its own until this endpoint explicitly enables it, since
every automatic run spends real LLM + embedding API budget with no human
watching. Calling /run manually is exactly as safe as a scheduled run:
every output lands on an existing human-approval gate (Feature 3's
:CandidateRule, Feature 6's :DuplicateCandidate), nothing auto-applies.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.dependencies import get_graphdb, get_neo4j
from app.schemas import ApiModel
from db.graphdb_client import GraphDBClient
from db.neo4j_client import Neo4jClient
from services import graph_maintenance_loop, maintenance_schedule_service, maintenance_scheduler

router = APIRouter(tags=["graph-maintenance"])


class LoopRunResponse(ApiModel):
    id: str
    graph_id: str
    mined_candidate_ids: list[str]
    reasoning_ran: bool
    reasoning_iterations: int | None
    reasoning_new_facts: int
    reasoning_converged_by: str | None
    duplicate_candidate_ids: list[str]
    active_rule_weights: dict[str, float]
    summary_text: str


class LoopRunsResponse(ApiModel):
    runs: list[LoopRunResponse]


def _to_response(s: graph_maintenance_loop.LoopRunSummary) -> LoopRunResponse:
    return LoopRunResponse(
        id=s.id, graph_id=s.graph_id, mined_candidate_ids=list(s.mined_candidate_ids),
        reasoning_ran=s.reasoning_ran, reasoning_iterations=s.reasoning_iterations,
        reasoning_new_facts=s.reasoning_new_facts, reasoning_converged_by=s.reasoning_converged_by,
        duplicate_candidate_ids=list(s.duplicate_candidate_ids), active_rule_weights=s.active_rule_weights,
        summary_text=s.as_summary_text(),
    )


@router.post("/graph-maintenance/{graph_id}/run", response_model=LoopRunResponse, response_model_by_alias=True)
def run_maintenance(
    graph_id: str,
    neo4j: Neo4jClient = Depends(get_neo4j),
    graphdb: GraphDBClient = Depends(get_graphdb),
    settings: Settings = Depends(get_settings),
) -> LoopRunResponse:
    summary = graph_maintenance_loop.run_maintenance_loop(neo4j, graphdb, settings, graph_id)
    return _to_response(summary)


@router.get("/graph-maintenance/{graph_id}/runs", response_model=LoopRunsResponse, response_model_by_alias=True)
def get_maintenance_runs(graph_id: str, neo4j: Neo4jClient = Depends(get_neo4j)) -> LoopRunsResponse:
    runs = graph_maintenance_loop.list_loop_runs(neo4j, graph_id)
    return LoopRunsResponse(runs=[_to_response(r) for r in runs])


class ScheduleResponse(ApiModel):
    graph_id: str
    enabled: bool
    interval_minutes: int
    last_run_at: str | None = None


class SetScheduleRequest(ApiModel):
    enabled: bool
    interval_minutes: int = 60


def _to_schedule_response(s: maintenance_schedule_service.MaintenanceSchedule) -> ScheduleResponse:
    return ScheduleResponse(graph_id=s.graph_id, enabled=s.enabled, interval_minutes=s.interval_minutes, last_run_at=s.last_run_at)


@router.get("/graph-maintenance/{graph_id}/schedule", response_model=ScheduleResponse, response_model_by_alias=True)
def get_schedule(graph_id: str, neo4j: Neo4jClient = Depends(get_neo4j)) -> ScheduleResponse:
    return _to_schedule_response(maintenance_schedule_service.get_schedule(neo4j, graph_id))


@router.post("/graph-maintenance/{graph_id}/schedule", response_model=ScheduleResponse, response_model_by_alias=True)
def set_schedule(graph_id: str, request: SetScheduleRequest, neo4j: Neo4jClient = Depends(get_neo4j)) -> ScheduleResponse:
    try:
        schedule = maintenance_schedule_service.set_schedule(
            neo4j, graph_id, enabled=request.enabled, interval_minutes=request.interval_minutes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    # Live-updates the running scheduler immediately -- a schedule change
    # takes effect now, not on the next process restart.
    maintenance_scheduler.sync_job(graph_id, enabled=schedule.enabled, interval_minutes=schedule.interval_minutes)
    return _to_schedule_response(schedule)
