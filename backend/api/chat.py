"""POST /chat/{graph_id} — real LLM console grounded in real graph state."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_llm, get_neo4j
from app.schemas import ApiModel
from db.neo4j_client import Neo4jClient
from llm.client import LLMClient
from services import chat_service

router = APIRouter(tags=["chat"])


class ChatRequest(ApiModel):
    message: str
    session_id: str | None = None


class ChatResponse(ApiModel):
    reply: str


@router.post("/chat/{graph_id}", response_model=ChatResponse, response_model_by_alias=True)
def chat(
    graph_id: str,
    request: ChatRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
    llm: LLMClient = Depends(get_llm),
) -> ChatResponse:
    # Default: one continuous session per graph, so existing callers that don't
    # send a session_id yet still get real conversational memory (PLAN.md §20 item 4).
    session_id = request.session_id or f"{graph_id}:default"
    reply = chat_service.answer(neo4j=neo4j, llm=llm, graph_id=graph_id, message=request.message, session_id=session_id)
    return ChatResponse(reply=reply)
