"""REST surface for cross-source memory search + preferences (PLAN.md §9),
for the MemoryInspector frontend component. Wraps the same
services/memory_service.py and services/preferences_store.py that
mcp_memory_server.py exposes to MCP clients -- no separate logic path.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.dependencies import get_embedder, get_neo4j
from app.schemas import ApiModel
from db.neo4j_client import Neo4jClient
from llm.embedder import EmbeddingClient
from services import memory_service, preferences_store

router = APIRouter(tags=["memory"])


class MemorySearchRequest(ApiModel):
    query: str


class MemoryHitItem(ApiModel):
    kind: str
    id: str
    text: str
    created_at: str | None = None


class MemorySearchResponse(ApiModel):
    hits: list[MemoryHitItem]


class PreferenceItem(ApiModel):
    key: str
    value: str


class PreferencesResponse(ApiModel):
    preferences: list[PreferenceItem]


class SavePreferenceRequest(ApiModel):
    value: str


@router.post("/memory/{graph_id}/search", response_model=MemorySearchResponse, response_model_by_alias=True)
def search_memory(
    graph_id: str, request: MemorySearchRequest,
    neo4j: Neo4jClient = Depends(get_neo4j), embedder: EmbeddingClient = Depends(get_embedder),
    settings: Settings = Depends(get_settings),
) -> MemorySearchResponse:
    hits = memory_service.search_memory(neo4j, graph_id=graph_id, query=request.query, embedder=embedder, settings=settings)
    return MemorySearchResponse(
        hits=[MemoryHitItem(kind=h.kind, id=h.id, text=h.text, created_at=h.created_at) for h in hits]
    )


@router.get("/memory/preferences", response_model=PreferencesResponse, response_model_by_alias=True)
def get_preferences(neo4j: Neo4jClient = Depends(get_neo4j)) -> PreferencesResponse:
    return PreferencesResponse(
        preferences=[PreferenceItem(key=r.key, value=r.value) for r in preferences_store.list_preferences(neo4j)]
    )


@router.put("/memory/preferences/{key}", response_model=PreferenceItem, response_model_by_alias=True)
def save_preference(key: str, request: SavePreferenceRequest, neo4j: Neo4jClient = Depends(get_neo4j)) -> PreferenceItem:
    preferences_store.save_preference(neo4j, key=key, value=request.value)
    return PreferenceItem(key=key, value=request.value)


@router.delete("/memory/preferences/{key}")
def delete_preference(key: str, neo4j: Neo4jClient = Depends(get_neo4j)) -> dict[str, bool]:
    preferences_store.delete_preference(neo4j, key=key)
    return {"deleted": True}
