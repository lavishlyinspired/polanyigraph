"""POST /chat/{graph_id} — real LLM console grounded in real graph state."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.dependencies import get_embedder, get_llm, get_neo4j
from app.schemas import ApiModel
from db.neo4j_client import Neo4jClient
from llm.client import LLMClient
from llm.embedder import EmbeddingClient
from services import chat_service, memory_config_service

router = APIRouter(tags=["chat"])


class ChatRequest(ApiModel):
    message: str
    session_id: str | None = None


class ChatResponse(ApiModel):
    reply: str


def _active_embedder(neo4j: Neo4jClient, embedder: EmbeddingClient) -> EmbeddingClient | None:
    # Only index embeddings when the native memory backend is active
    # (GRAPHITI_INTEGRATION_PLAN.md §4 Option A) -- "graphiti" owns its own
    # embedding pipeline instead.
    return embedder if memory_config_service.get_backend(neo4j) == "native" else None


@router.post("/chat/{graph_id}", response_model=ChatResponse, response_model_by_alias=True)
def chat(
    graph_id: str,
    request: ChatRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
    llm: LLMClient = Depends(get_llm),
    embedder: EmbeddingClient = Depends(get_embedder),
) -> ChatResponse:
    # Default: one continuous session per graph, so existing callers that don't
    # send a session_id yet still get real conversational memory (PLAN.md §20 item 4).
    session_id = request.session_id or f"{graph_id}:default"
    reply = chat_service.answer(
        neo4j=neo4j, llm=llm, graph_id=graph_id, message=request.message, session_id=session_id,
        embedder=_active_embedder(neo4j, embedder),
    )
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
    embedder: EmbeddingClient = Depends(get_embedder),
) -> StreamingResponse:
    session_id = request.session_id or f"{graph_id}:default"
    active_embedder = _active_embedder(neo4j, embedder)

    def event_stream() -> Iterator[str]:
        for chunk in chat_service.stream_answer(
            neo4j=neo4j, llm=llm, graph_id=graph_id, message=request.message, session_id=session_id,
            embedder=active_embedder,
        ):
            yield _sse(chunk)
        yield _sse("[DONE]")

    return StreamingResponse(event_stream(), media_type="text/event-stream")
