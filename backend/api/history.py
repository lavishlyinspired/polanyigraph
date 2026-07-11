"""GET /history/{graph_id} — review what was posted into a graph over time."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_neo4j
from app.schemas import ApiModel
from db.neo4j_client import Neo4jClient
from services import history_service

router = APIRouter(tags=["history"])


class IngestEventResponse(ApiModel):
    id: str
    text: str
    entity_count: int
    relationship_count: int
    dropped_count: int
    created_at: str


class HistoryResponse(ApiModel):
    events: list[IngestEventResponse]


@router.get("/history/{graph_id}", response_model=HistoryResponse, response_model_by_alias=True)
def get_history(graph_id: str, neo4j: Neo4jClient = Depends(get_neo4j)) -> HistoryResponse:
    events = history_service.list_ingest_events(neo4j, graph_id)
    return HistoryResponse(
        events=[
            IngestEventResponse(
                id=e.id, text=e.text, entity_count=e.entity_count,
                relationship_count=e.relationship_count, dropped_count=e.dropped_count,
                created_at=e.created_at,
            )
            for e in events
        ]
    )
