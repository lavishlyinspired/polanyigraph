"""Embedding client (GRAPHITI_INTEGRATION_PLAN.md Option A/B).

OpenAI-compatible embeddings endpoint, same protocol as llm/client.py.
Defaults to the NVIDIA endpoint already configured for chat completions
(confirmed live to serve real embedding models -- nvidia/nv-embedqa-e5-v5,
1024-dim) via an independent base_url/api_key so it can be pointed elsewhere
without touching the chat LLM config.

NVIDIA's NIM embedding models are asymmetric (query vs passage) -- pass
input_type="query" when embedding a search query, "passage" when embedding
content being stored for later retrieval, to match how the model was trained.
"""

from __future__ import annotations

from typing import Literal

from openai import OpenAI

from app.config import Settings

InputType = Literal["query", "passage"]


class EmbeddingClient:
    def __init__(self, settings: Settings) -> None:
        self._model = settings.embedding_model
        self._dimensions = settings.embedding_dimensions
        self._client = OpenAI(
            base_url=settings.resolved_embedding_base_url,
            api_key=settings.resolved_embedding_api_key,
        )

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, texts: list[str], *, input_type: InputType) -> list[list[float]]:
        if not texts:
            return []
        resp = self._client.embeddings.create(
            model=self._model,
            input=texts,
            extra_body={"input_type": input_type, "truncate": "END"},
        )
        return [item.embedding for item in resp.data]

    def verify(self) -> bool:
        self.embed(["connectivity check"], input_type="query")
        return True
