"""POST /agent/{graph_id} — LangGraph-orchestrated extractor->reasoner->
responder (MVP_PLAN.md Phase 6, the last remaining original MVP item).

One user message in, one grounded natural-language reply out -- the agent
does real extraction + real reasoning internally (backend/agents/graph.py)
and reports what actually happened, not a canned response.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.dependencies import get_agent_graph
from app.schemas import ApiModel

router = APIRouter(tags=["agent"])


class AgentRequest(ApiModel):
    text: str
    session_id: str | None = None


class AgentResponse(ApiModel):
    reply: str
    intent: str
    entities_extracted: int
    relationships_extracted: int
    facts_derived: int
    enrichment_fact_texts: list[str] = []
    query_results: list[str] = []
    query_error: str = ""
    memory_hits: list[str] = []
    discovered_skills: list[str] = []


@router.post("/agent/{graph_id}", response_model=AgentResponse, response_model_by_alias=True)
def run_agent(graph_id: str, request: AgentRequest, agent: Any = Depends(get_agent_graph)) -> AgentResponse:
    thread_id = request.session_id or f"{graph_id}:default"
    result = agent.invoke(
        {
            "graph_id": graph_id,
            "text": request.text,
            "intent": "",
            "intents": [],
            "entities_extracted": 0,
            "relationships_extracted": 0,
            "facts_derived": 0,
            "fact_texts": [],
            "enrichment_fact_texts": [],
            "query_results": [],
            "query_error": "",
            "memory_hits": [],
            "discovered_skills": [],
            "discovered_skill_scores": [],
            "partial_answers": {},
            "combined_answer": "",
            "reply": "",
        },
        config={"configurable": {"thread_id": thread_id}},
    )
    return AgentResponse(
        reply=result["reply"],
        intent=result["intent"],
        entities_extracted=result["entities_extracted"],
        relationships_extracted=result["relationships_extracted"],
        facts_derived=result["facts_derived"],
        enrichment_fact_texts=result["enrichment_fact_texts"],
        query_results=result["query_results"],
        query_error=result["query_error"],
        memory_hits=result["memory_hits"],
        discovered_skills=result["discovered_skills"],
    )
