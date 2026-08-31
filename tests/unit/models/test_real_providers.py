"""Tests for real provider implementations."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.exceptions import (
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from app.models.catalog import ProviderCatalog
from app.models.providers import LLMMessage
from app.models.real_providers import (
    AnthropicProvider,
    GoogleProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
    register_all_providers,
)


class TestOpenAICompatibleProvider:
    @pytest.fixture
    def provider(self) -> OpenAICompatibleProvider:
        return OpenAICompatibleProvider(
            name="test-provider",
            model="test-model",
            base_url="https://api.example.com/v1",
            api_key="test-key",
        )

    @pytest.mark.asyncio
    async def test_complete_success(self, provider: OpenAICompatibleProvider) -> None:
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": "Hello, world!"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }
            mock_post.return_value = mock_resp

            messages = [LLMMessage(role="user", content="Hello")]
            result = await provider.complete(messages)

            assert result.text == "Hello, world!"
            assert result.provider == "test-provider"
            assert result.model == "test-model"
            assert result.prompt_tokens == 10
            assert result.completion_tokens == 5
            assert result.total_tokens == 15

    @pytest.mark.asyncio
    async def test_complete_timeout(self, provider: OpenAICompatibleProvider) -> None:
        import httpx

        with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("timeout")):
            messages = [LLMMessage(role="user", content="Hello")]
            with pytest.raises(ProviderTimeoutError):
                await provider.complete(messages)

    @pytest.mark.asyncio
    async def test_complete_rate_limit(self, provider: OpenAICompatibleProvider) -> None:
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 429
            mock_resp.headers = {"retry-after": "5"}
            mock_post.return_value = mock_resp

            messages = [LLMMessage(role="user", content="Hello")]
            with pytest.raises(ProviderRateLimitError):
                await provider.complete(messages)


class TestAnthropicProvider:
    @pytest.fixture
    def provider(self) -> AnthropicProvider:
        return AnthropicProvider(api_key="test-key")

    @pytest.mark.asyncio
    async def test_convert_messages(self, provider: AnthropicProvider) -> None:
        messages = [
            LLMMessage(role="system", content="You are helpful"),
            LLMMessage(role="user", content="Hello"),
            LLMMessage(role="assistant", content="Hi there"),
            LLMMessage(role="user", content="How are you?"),
        ]
        system, anthropic_messages = provider._convert_messages(messages)
        assert system == "You are helpful"
        assert len(anthropic_messages) == 3
        assert anthropic_messages[0] == {"role": "user", "content": "Hello"}
        assert anthropic_messages[1] == {"role": "assistant", "content": "Hi there"}
        assert anthropic_messages[2] == {"role": "user", "content": "How are you?"}


class TestOllamaProvider:
    @pytest.fixture
    def provider(self) -> OllamaProvider:
        return OllamaProvider(name="ollama", model="llama3.1:8b", base_url="http://localhost:11434")

    @pytest.mark.asyncio
    async def test_complete_fallback_success(self, provider: OllamaProvider) -> None:
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": "Ollama response"}}],
                "usage": {"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12},
            }
            mock_post.return_value = mock_resp

            # Mock ollama import to fail so it falls back to HTTP
            with patch.dict("sys.modules", {"ollama": None}):
                messages = [LLMMessage(role="user", content="Hello")]
                result = await provider.complete(messages)

            assert result.text == "Ollama response"
            assert result.provider == "ollama"


class TestGoogleProvider:
    @pytest.fixture
    def provider(self) -> GoogleProvider:
        return GoogleProvider(api_key="test-key")

    @pytest.mark.asyncio
    async def test_complete_success(self, provider: GoogleProvider) -> None:
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "candidates": [{"content": {"parts": [{"text": "Gemini response"}]}}],
                "usageMetadata": {
                    "promptTokenCount": 12,
                    "candidatesTokenCount": 6,
                    "totalTokenCount": 18,
                },
            }
            mock_post.return_value = mock_resp

            messages = [LLMMessage(role="user", content="Hello")]
            result = await provider.complete(messages)

            assert result.text == "Gemini response"
            assert result.provider == "google"
            assert result.prompt_tokens == 12
            assert result.completion_tokens == 6
            assert result.total_tokens == 18


class TestRegisterAllProviders:
    def test_register_all_providers(self) -> None:
        catalog = ProviderCatalog()
        register_all_providers(catalog)

        # At minimum, ollama should always be registered (no API key needed)
        assert "ollama" in catalog.names()

    def test_register_providers_with_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Set some env vars to trigger cloud provider registration
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        catalog = ProviderCatalog()
        register_all_providers(catalog)

        assert "ollama" in catalog.names()
        assert "openai" in catalog.names()
        assert "anthropic" in catalog.names()


class TestDefaultCatalog:
    def test_default_catalog_has_mock_and_ollama(self) -> None:
        from app.models.catalog import default_catalog

        catalog = default_catalog()
        names = catalog.names()
        assert "mock" in names
        assert "ollama" in names
