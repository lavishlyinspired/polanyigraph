"""REST surface for real runtime skills (PLAN.md §13.2), for the SkillManager
frontend component. Wraps the same agents/skill_store.py Discovery/Activation
and services/skill_activation_store.py real persisted "active" state that
mcp_skills_server.py exposes to MCP clients -- no separate logic path.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from agents import skill_store
from app.dependencies import get_neo4j
from app.schemas import ApiModel
from db.neo4j_client import Neo4jClient
from services import skill_activation_store

router = APIRouter(tags=["skills"])


class SkillItem(ApiModel):
    name: str
    description: str
    active: bool


class SkillsResponse(ApiModel):
    skills: list[SkillItem]


class SkillContentResponse(ApiModel):
    name: str
    content: str


class SkillActivateResponse(ApiModel):
    name: str
    active: bool


@router.get("/skills", response_model=SkillsResponse, response_model_by_alias=True)
def get_skills(neo4j: Neo4jClient = Depends(get_neo4j)) -> SkillsResponse:
    active = skill_activation_store.list_active_skills(neo4j)
    return SkillsResponse(
        skills=[SkillItem(name=m.name, description=m.description, active=m.name in active) for m in skill_store.scan()]
    )


@router.get("/skills/{name}/content", response_model=SkillContentResponse, response_model_by_alias=True)
def get_skill_content(name: str) -> SkillContentResponse:
    try:
        content = skill_store.load(name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return SkillContentResponse(name=name, content=content)


@router.post("/skills/{name}/activate", response_model=SkillActivateResponse, response_model_by_alias=True)
def activate_skill(name: str, neo4j: Neo4jClient = Depends(get_neo4j)) -> SkillActivateResponse:
    known_names = {m.name for m in skill_store.scan()}
    if name not in known_names:
        raise HTTPException(status_code=404, detail=f"No runtime skill named '{name}' in {skill_store.SKILLS_DIR}")
    skill_activation_store.activate_skill(neo4j, name=name)
    return SkillActivateResponse(name=name, active=True)
