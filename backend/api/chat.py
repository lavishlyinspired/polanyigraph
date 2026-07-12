"""POST /chat/{graph_id} — real LLM console grounded in real graph state."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

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


def _sse(data: str) -> str:
    # SSE framing: each line of the payload gets its own "data:" prefix,
    # event terminated by a blank line.
    return "".join(f"data: {line}\n" for line in data.split("\n")) + "\n"


@router.post("/chat/{graph_id}/stream")
def chat_stream(
    graph_id: str,
    request: ChatRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
    llm: LLMClient = Depends(get_llm),
) -> StreamingResponse:
    session_id = request.session_id or f"{graph_id}:default"

    def event_stream() -> Iterator[str]:
        for chunk in chat_service.stream_answer(
            neo4j=neo4j, llm=llm, graph_id=graph_id, message=request.message, session_id=session_id
        ):
            yield _sse(chunk)
        yield _sse("[DONE]")

    return StreamingResponse(event_stream(), media_type="text/event-stream")
