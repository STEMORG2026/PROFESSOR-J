"""Provider catalog — curated defaults plus dynamic discovery."""

from __future__ import annotations

import logging
import os

from app.models.cloud_providers import (
    GoogleAIProvider,
    NVIDIANIMProvider,
    OpenRouterProvider,
)
from app.models.providers import LLMProvider, MockProvider

logger = logging.getLogger(__name__)


class ProviderCatalog:
    """Curated defaults + runtime-registered providers."""

    def __init__(self, providers: list[LLMProvider] | None = None) -> None:
        self._providers: dict[str, LLMProvider] = {}
        self._order: list[str] = []
        for provider in providers or []:
            self.register(provider)

    def register(self, provider: LLMProvider) -> None:
        """Register a provider under its name (dynamic discovery entry point)."""
        if provider.name in self._providers:
            logger.warning("Overwriting catalog provider: %s", provider.name)
        if provider.name not in self._providers:
            self._order.append(provider.name)
        self._providers[provider.name] = provider

    def get(self, name: str) -> LLMProvider | None:
        return self._providers.get(name)

    def names(self) -> list[str]:
        return list(self._order)

    def all(self) -> list[LLMProvider]:
        return [self._providers[n] for n in self._order]

    def count(self) -> int:
        return len(self._providers)

    def register_from_env(self) -> int:
        """Register providers from environment variables. Returns count of registered providers."""
        count = 0

        # OpenRouter
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        if openrouter_key:
            self.register(
                OpenRouterProvider(
                    name="openrouter",
                    model="openrouter/auto",
                    api_key=openrouter_key,
                )
            )
            count += 1

        # NVIDIA NIM
        nim_key = os.getenv("NVIDIA_NIM_API_KEY")
        if nim_key:
            self.register(
                NVIDIANIMProvider(
                    name="nvidia_nim",
                    model="nvidia/nemotron-3-ultra",
                    api_key=nim_key,
                )
            )
            count += 1

        # Google AI
        google_key = os.getenv("GOOGLE_AI_API_KEY")
        if google_key:
            self.register(
                GoogleAIProvider(
                    name="google_ai",
                    model="gemini-1.5-pro",
                    api_key=google_key,
                )
            )
            count += 1

        return count


def default_catalog() -> ProviderCatalog:
    """Build the curated default catalog (local-first, cloud via env)."""
    catalog = ProviderCatalog()
    # Local inference options (no API key required).
    catalog.register(MockProvider(name="mock", model="mock-model"))
    # Register cloud providers from environment
    catalog.register_from_env()
    return catalog


__all__ = ["ProviderCatalog", "default_catalog"]
