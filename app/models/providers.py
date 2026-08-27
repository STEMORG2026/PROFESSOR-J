"""Typed LLM providers — the pluggable model-pool interface.

All providers implement :class:`LLMProvider`. A :class:`MockProvider` provides a
deterministic, dependency-free implementation used in tests and as a dev
fallback; :class:`OpenAICompatProvider` targets any OpenAI-compatible
``/chat/completions`` endpoint over HTTP.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LLMMessage:
    role: str  # user | assistant | system
    content: str


@dataclass(frozen=True, slots=True)
class LLMResult:
    text: str
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def usage(self) -> dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


class LLMProvider(ABC):
    """Interface every provider implements."""

    name: str
    model: str

    @abstractmethod
    async def complete(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResult:
        """Complete a chat-style conversation and return the assistant response."""
        raise NotImplementedError

    def __repr__(self) -> str:  # pragma: no cover
        return f"{type(self).__name__}(name={self.name!r}, model={self.model!r})"


class MockProvider(LLMProvider):
    """Deterministic provider for tests and local development.

    Echoes a canned response built from the last user message, so behaviour is
    fully reproducible without any network dependency.
    """

    def __init__(self, name: str = "mock", model: str = "mock-model") -> None:
        self.name = name
        self.model = model

    async def complete(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResult:
        user_text = next((m.content for m in reversed(messages) if m.role == "user"), "")
        return LLMResult(
            text=f"[mock:{self.name}] processed {len(messages)} message(s); last={user_text[:64]}",
            provider=self.name,
            model=self.model,
            prompt_tokens=sum(len(m.content.split()) for m in messages),
            completion_tokens=8,
            total_tokens=16,
            metadata={"mock": True},
        )


class OpenAICompatProvider(LLMProvider):
    """Calls any OpenAI-compatible ``/chat/completions`` endpoint.

    ``base_url`` may point at OpenAI, OpenRouter, Ollama, llama.cpp, vLLM, etc.
    Authentication via an optional bearer ``api_key``.
    """

    def __init__(
        self,
        name: str,
        model: str,
        base_url: str,
        api_key: str | None = None,
        *,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.name = name
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    async def complete(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResult:
        import httpx

        url = f"{self.base_url}/chat/completions"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        payload.update(kwargs.get("params", {}))
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        return LLMResult(
            text=text,
            provider=self.name,
            model=self.model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )
