"""Real LLM provider implementations for the model pool.

Ported from JARVIS patterns, adapted to PROFESSOR-J's LLMProvider interface.
Each provider wraps an OpenAI-compatible or native client behind the abstract interface.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

import httpx

from app.exceptions import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.models.providers import LLMMessage, LLMProvider, LLMResult

if TYPE_CHECKING:
    from app.models.catalog import ProviderCatalog

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(LLMProvider):
    """Generic provider for any OpenAI-compatible /chat/completions endpoint.

    Covers: OpenAI, OpenRouter, Groq, Together, NVIDIA NIM, GitHub Models,
    Cloudflare AI, Cerebras, Mistral, Cohere (with chat endpoint), etc.
    """

    def __init__(
        self,
        name: str,
        model: str,
        base_url: str,
        api_key: str | None = None,
        *,
        timeout_seconds: float = 60.0,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.name = name
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.extra_headers = extra_headers or {}

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json", **self.extra_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def complete(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResult:
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        payload.update(kwargs.get("params", {}))

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(url, json=payload, headers=self._headers())
        except httpx.TimeoutException as e:
            raise ProviderTimeoutError(
                provider=self.name, timeout=self.timeout_seconds, message=str(e)
            ) from e
        except httpx.NetworkError as e:
            raise ProviderUnavailableError(provider=self.name, message=str(e)) from e

        if resp.status_code == 401:
            raise ProviderAuthError(provider=self.name, message="Invalid API key")
        if resp.status_code == 429:
            retry_after = resp.headers.get("retry-after", "1")
            raise ProviderRateLimitError(
                provider=self.name, message="Rate limited", retry_after=int(retry_after)
            )
        if resp.status_code >= 500:
            raise ProviderUnavailableError(provider=self.name, message=f"HTTP {resp.status_code}")

        resp.raise_for_status()
        data = resp.json()

        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return LLMResult(
            text=text,
            provider=self.name,
            model=self.model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )


class AnthropicProvider(LLMProvider):
    """Anthropic (Claude) provider - native API format."""

    def __init__(
        self,
        name: str = "anthropic",
        model: str = "claude-3-5-sonnet-20241022",
        api_key: str | None = None,
        *,
        timeout_seconds: float = 120.0,
    ) -> None:
        self.name = name
        self.model = model
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.timeout_seconds = timeout_seconds
        self.base_url = "https://api.anthropic.com/v1"

    def _headers(self) -> dict[str, str]:
        api_key = self.api_key or ""
        return {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def _convert_messages(
        self, messages: list[LLMMessage]
    ) -> tuple[str | None, list[dict[str, str]]]:
        system_parts: list[str] = []
        anthropic_messages: list[dict[str, str]] = []
        for m in messages:
            if m.role == "system":
                system_parts.append(m.content)
                continue
            role = "assistant" if m.role == "assistant" else "user"
            if anthropic_messages and anthropic_messages[-1]["role"] == role:
                anthropic_messages[-1]["content"] += f"\n\n{m.content}"
            else:
                anthropic_messages.append({"role": role, "content": m.content})
        system = "\n\n".join(system_parts) if system_parts else None
        return system, anthropic_messages

    async def complete(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResult:
        system, anthropic_messages = self._convert_messages(messages)
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": kwargs.get("max_tokens", 4096),
        }
        if system:
            payload["system"] = system
        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]
        if "top_p" in kwargs:
            payload["top_p"] = kwargs["top_p"]
        if "top_k" in kwargs:
            payload["top_k"] = kwargs["top_k"]

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(
                    f"{self.base_url}/messages", json=payload, headers=self._headers()
                )
        except httpx.TimeoutException as e:
            raise ProviderTimeoutError(
                provider=self.name, timeout=self.timeout_seconds, message=str(e)
            ) from e
        except httpx.NetworkError as e:
            raise ProviderUnavailableError(provider=self.name, message=str(e)) from e

        if resp.status_code == 401:
            raise ProviderAuthError(provider=self.name, message="Invalid API key")
        if resp.status_code == 429:
            retry_after = resp.headers.get("retry-after", "1")
            raise ProviderRateLimitError(
                provider=self.name, message="Rate limited", retry_after=int(retry_after)
            )
        if resp.status_code >= 500:
            raise ProviderUnavailableError(provider=self.name, message=f"HTTP {resp.status_code}")

        resp.raise_for_status()
        data = resp.json()

        content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")

        usage = data.get("usage", {})
        return LLMResult(
            text=content,
            provider=self.name,
            model=self.model,
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
            total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        )


class OllamaProvider(LLMProvider):
    """Ollama local inference provider.

    Uses native ollama python client or OpenAI-compatible endpoint fallback.
    """

    def __init__(
        self,
        name: str = "ollama",
        model: str = "llama3.1:8b",
        base_url: str = "http://localhost:11434",
        *,
        timeout_seconds: float = 120.0,
    ) -> None:
        self.name = name
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def complete(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResult:
        # Try native ollama client first, fall back to OpenAI-compatible endpoint
        try:
            import ollama  # type: ignore[import-not-found]

            client = ollama.Client(host=self.base_url)
            response = client.chat(
                model=self.model,
                messages=[{"role": m.role, "content": m.content} for m in messages],
            )
            content = response.get("message", {}).get("content", "")
            return LLMResult(text=content, provider=self.name, model=self.model)
        except ImportError:
            # Fall back to OpenAI-compatible endpoint
            pass
        except Exception:
            # Fall back to OpenAI-compatible endpoint
            pass

        # OpenAI-compatible fallback
        url = f"{self.base_url}/v1/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        payload.update(kwargs.get("params", {}))

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(
                    url, json=payload, headers={"Content-Type": "application/json"}
                )
        except httpx.TimeoutException as e:
            raise ProviderTimeoutError(
                provider=self.name, timeout=self.timeout_seconds, message=str(e)
            ) from e
        except httpx.NetworkError as e:
            raise ProviderUnavailableError(provider=self.name, message=str(e)) from e

        if resp.status_code == 429:
            retry_after = resp.headers.get("retry-after", "1")
            raise ProviderRateLimitError(
                provider=self.name, message="Rate limited", retry_after=int(retry_after)
            )
        if resp.status_code >= 500:
            raise ProviderUnavailableError(provider=self.name, message=f"HTTP {resp.status_code}")

        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return LLMResult(
            text=text,
            provider=self.name,
            model=self.model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )


class GoogleProvider(LLMProvider):
    """Google (Gemini) provider - native API format."""

    def __init__(
        self,
        name: str = "google",
        model: str = "gemini-1.5-pro",
        api_key: str | None = None,
        *,
        timeout_seconds: float = 120.0,
    ) -> None:
        self.name = name
        self.model = model
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.timeout_seconds = timeout_seconds
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    async def complete(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResult:
        # Convert to Gemini format
        contents: list[dict[str, Any]] = []
        for m in messages:
            role = "model" if m.role == "assistant" else "user"
            if m.role == "system":
                # Prepend system to first user message
                if contents and contents[-1]["role"] == "user":
                    contents[-1]["parts"][0]["text"] = (
                        m.content + "\n\n" + contents[-1]["parts"][0]["text"]
                    )
                else:
                    contents.insert(0, {"role": "user", "parts": [{"text": m.content}]})
            else:
                contents.append({"role": role, "parts": [{"text": m.content}]})

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": kwargs.get("max_tokens", 4096),
                "temperature": kwargs.get("temperature", 0.7),
            },
        }
        if "top_p" in kwargs:
            payload["generationConfig"]["topP"] = kwargs["top_p"]
        if "top_k" in kwargs:
            payload["generationConfig"]["topK"] = kwargs["top_k"]

        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(
                    url, json=payload, headers={"Content-Type": "application/json"}
                )
        except httpx.TimeoutException as e:
            raise ProviderTimeoutError(
                provider=self.name, timeout=self.timeout_seconds, message=str(e)
            ) from e
        except httpx.NetworkError as e:
            raise ProviderUnavailableError(provider=self.name, message=str(e)) from e

        if resp.status_code == 401:
            raise ProviderAuthError(provider=self.name, message="Invalid API key")
        if resp.status_code == 429:
            retry_after = resp.headers.get("retry-after", "1")
            raise ProviderRateLimitError(
                provider=self.name, message="Rate limited", retry_after=int(retry_after)
            )
        if resp.status_code >= 500:
            raise ProviderUnavailableError(provider=self.name, message=f"HTTP {resp.status_code}")

        resp.raise_for_status()
        data = resp.json()

        text = ""
        if "candidates" in data and data["candidates"]:
            parts = data["candidates"][0].get("content", {}).get("parts", [])
            for part in parts:
                if "text" in part:
                    text += part["text"]

        usage = data.get("usageMetadata", {})
        return LLMResult(
            text=text,
            provider=self.name,
            model=self.model,
            prompt_tokens=usage.get("promptTokenCount", 0),
            completion_tokens=usage.get("candidatesTokenCount", 0),
            total_tokens=usage.get("totalTokenCount", 0),
        )


def register_all_providers(catalog: ProviderCatalog) -> None:
    """Register all available providers with the catalog.

    Only registers providers that have their required environment variables set.
    """
    # Local-first (no API key required)
    catalog.register(OllamaProvider(name="ollama", model="llama3.1:8b"))

    # Cloud providers (require API keys from environment)
    if os.getenv("OPENAI_API_KEY"):
        catalog.register(
            OpenAICompatibleProvider(
                name="openai",
                model="gpt-4o-mini",
                base_url="https://api.openai.com/v1",
                api_key=os.getenv("OPENAI_API_KEY"),
            )
        )
    if os.getenv("OPENROUTER_API_KEY"):
        catalog.register(
            OpenAICompatibleProvider(
                name="openrouter",
                model="openai/gpt-4o-mini",
                base_url="https://openrouter.ai/api/v1",
                api_key=os.getenv("OPENROUTER_API_KEY"),
                extra_headers={
                    "HTTP-Referer": "https://github.com/Er-Sajan-PLG/PROFESSOR-J",
                    "X-Title": "PROFESSOR-J",
                },
            )
        )
    if os.getenv("GROQ_API_KEY"):
        catalog.register(
            OpenAICompatibleProvider(
                name="groq",
                model="llama-3.1-8b-instant",
                base_url="https://api.groq.com/openai/v1",
                api_key=os.getenv("GROQ_API_KEY"),
            )
        )
    if os.getenv("TOGETHER_API_KEY"):
        catalog.register(
            OpenAICompatibleProvider(
                name="together",
                model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
                base_url="https://api.together.xyz/v1",
                api_key=os.getenv("TOGETHER_API_KEY"),
            )
        )
    if os.getenv("ANTHROPIC_API_KEY"):
        catalog.register(AnthropicProvider())
    if os.getenv("GOOGLE_API_KEY"):
        catalog.register(GoogleProvider())
    if os.getenv("MISTRAL_API_KEY"):
        catalog.register(
            OpenAICompatibleProvider(
                name="mistral",
                model="mistral-small-latest",
                base_url="https://api.mistral.ai/v1",
                api_key=os.getenv("MISTRAL_API_KEY"),
            )
        )
    if os.getenv("COHERE_API_KEY"):
        catalog.register(
            OpenAICompatibleProvider(
                name="cohere",
                model="command-r-plus",
                base_url="https://api.cohere.com/v1",
                api_key=os.getenv("COHERE_API_KEY"),
            )
        )
    if os.getenv("NVIDIA_NIM_API_KEY"):
        catalog.register(
            OpenAICompatibleProvider(
                name="nvidia-nim",
                model="meta/llama-3.1-8b-instruct",
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=os.getenv("NVIDIA_NIM_API_KEY"),
            )
        )
    if os.getenv("CEREBRAS_API_KEY"):
        catalog.register(
            OpenAICompatibleProvider(
                name="cerebras",
                model="llama3.1-8b",
                base_url="https://api.cerebras.ai/v1",
                api_key=os.getenv("CEREBRAS_API_KEY"),
            )
        )
    if os.getenv("GITHUB_MODELS_TOKEN"):
        catalog.register(
            OpenAICompatibleProvider(
                name="github-models",
                model="gpt-4o-mini",
                base_url="https://models.inference.ai.azure.com",
                api_key=os.getenv("GITHUB_MODELS_TOKEN"),
            )
        )
    if os.getenv("HF_API_TOKEN"):
        catalog.register(
            OpenAICompatibleProvider(
                name="huggingface",
                model="meta-llama/Meta-Llama-3.1-8B-Instruct",
                base_url="https://api-inference.huggingface.co/models/meta-llama/Meta-Llama-3.1-8B-Instruct",
                api_key=os.getenv("HF_API_TOKEN"),
            )
        )
