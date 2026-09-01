"""Cloud provider implementations — OpenRouter, NVIDIA NIM, Google AI."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from app.models.providers import LLMMessage, LLMProvider, LLMResult

logger = logging.getLogger(__name__)


class OpenRouterProvider(LLMProvider):
    """OpenRouter provider with access to multiple models via single API key."""

    def __init__(
        self,
        name: str,
        model: str,
        api_key: str | None = None,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout_seconds: float = 60.0,
    ) -> None:
        self.name = name
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.timeout_seconds = timeout_seconds

    async def complete(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResult:
        if not self.api_key:
            raise RuntimeError("OpenRouter API key not configured")

        # Convert LLMMessage to dict format for API
        messages_dict = [{"role": msg.role, "content": msg.content} for msg in messages]

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://professor-j.app",
            "X-Title": "PROFESSOR-J",
        }
        payload = {
            "model": self.model,
            "messages": messages_dict,
            **kwargs,
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        text = choice["message"]["content"]
        usage = data.get("usage", {})

        return LLMResult(
            text=text,
            provider=self.name,
            model=self.model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            metadata={"finish_reason": choice.get("finish_reason")},
        )


class NVIDIANIMProvider(LLMProvider):
    """NVIDIA NIM provider for accelerated inference."""

    def __init__(
        self,
        name: str,
        model: str,
        api_key: str | None = None,
        base_url: str = "https://integrate.api.nvidia.com/v1",
        timeout_seconds: float = 60.0,
    ) -> None:
        self.name = name
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.getenv("NVIDIA_NIM_API_KEY")
        self.timeout_seconds = timeout_seconds

    async def complete(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResult:
        if not self.api_key:
            raise RuntimeError("NVIDIA NIM API key not configured")

        messages_dict = [{"role": msg.role, "content": msg.content} for msg in messages]

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages_dict,
            **kwargs,
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        text = choice["message"]["content"]
        usage = data.get("usage", {})

        return LLMResult(
            text=text,
            provider=self.name,
            model=self.model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            metadata={"finish_reason": choice.get("finish_reason")},
        )


class GoogleAIProvider(LLMProvider):
    """Google AI (Gemini) provider supporting free tier and Pro subscription."""

    def __init__(
        self,
        name: str,
        model: str,
        api_key: str | None = None,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout_seconds: float = 60.0,
    ) -> None:
        self.name = name
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.getenv("GOOGLE_AI_API_KEY")
        self.timeout_seconds = timeout_seconds

    def _format_messages(self, messages: list[LLMMessage]) -> list[dict[str, Any]]:
        """Convert standard messages to Google AI format."""
        formatted = []
        for msg in messages:
            role = msg.role
            content = msg.content
            if role == "system":
                formatted.append({"role": "user", "parts": [{"text": content}]})
                formatted.append({"role": "model", "parts": [{"text": "Understood."}]})
            elif role == "user":
                formatted.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                formatted.append({"role": "model", "parts": [{"text": content}]})
        return formatted

    async def complete(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResult:
        if not self.api_key:
            raise RuntimeError("Google AI API key not configured")

        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}

        formatted_messages = self._format_messages(messages)

        payload = {
            "contents": formatted_messages,
            "generationConfig": {
                "temperature": kwargs.get("temperature", 0.7),
                "maxOutputTokens": kwargs.get("max_tokens", 2048),
                "topP": kwargs.get("top_p", 0.95),
                "topK": kwargs.get("top_k", 40),
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        if "candidates" not in data or not data["candidates"]:
            raise RuntimeError("No candidates returned from Google AI")

        candidate = data["candidates"][0]
        text = candidate["content"]["parts"][0]["text"] if candidate["content"]["parts"] else ""
        usage = data.get("usageMetadata", {})

        return LLMResult(
            text=text,
            provider=self.name,
            model=self.model,
            prompt_tokens=usage.get("promptTokenCount", 0),
            completion_tokens=usage.get("candidatesTokenCount", 0),
            total_tokens=usage.get("totalTokenCount", 0),
            metadata={"finish_reason": candidate.get("finishReason")},
        )


def create_provider_from_config(config: dict[str, Any]) -> LLMProvider | None:
    """Factory to create provider from config dict."""
    provider_type = config.get("type", "").lower()
    name = config.get("name", "")
    model = config.get("model", "")
    api_key = config.get("api_key")

    if provider_type == "openrouter":
        return OpenRouterProvider(
            name=name or "openrouter",
            model=model,
            api_key=api_key,
            base_url=config.get("base_url", "https://openrouter.ai/api/v1"),
        )
    elif provider_type == "nvidia_nim":
        return NVIDIANIMProvider(
            name=name or "nvidia_nim",
            model=model,
            api_key=api_key,
            base_url=config.get("base_url", "https://integrate.api.nvidia.com/v1"),
        )
    elif provider_type == "google_ai":
        return GoogleAIProvider(
            name=name or "google_ai",
            model=model,
            api_key=api_key,
            base_url=config.get("base_url", "https://generativelanguage.googleapis.com/v1beta"),
        )
    return None


__all__ = [
    "OpenRouterProvider",
    "NVIDIANIMProvider",
    "GoogleAIProvider",
    "create_provider_from_config",
]
