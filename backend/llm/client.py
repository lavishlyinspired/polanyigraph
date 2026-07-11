"""Provider-agnostic LLM client.

Uses the OpenAI-compatible protocol so any compatible endpoint works. The
configured default is NVIDIA-hosted GLM (``z-ai/glm-5.2``) from the environment;
switch model/base_url in config to use a different provider. No vendor is
hardcoded in call sites — they depend on this interface only.
"""

from __future__ import annotations

from typing import Any

from openai import OpenAI

from app.config import Settings


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self._model = settings.nvidia_model
        self._client = OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.nvidia_api_key,
        )

    @property
    def model(self) -> str:
        return self._model

    def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        """Return the raw assistant message content for a JSON-producing prompt.

        Parsing/validation is the caller's responsibility (extraction validates
        against the ontology schema).
        """
        resp = self._client.chat.completions.create(
            model=self._model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""

    def verify(self) -> bool:
        self._client.models.list()
        return True

    def raw(self) -> Any:
        return self._client
