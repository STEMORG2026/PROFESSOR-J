"""Provider catalog — curated defaults plus dynamic discovery.

The router picks a healthy provider from the catalog. Defaults are curated for
the common local + cloud cases; callers may register additional providers at
runtime (dynamic discovery) without hardcoding fallbacks.
"""

from __future__ import annotations

import logging

from app.models.providers import LLMProvider, MockProvider
from app.models.real_providers import register_all_providers

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


def default_catalog() -> ProviderCatalog:
    """Build the curated default catalog (local-first, cloud via env)."""
    catalog = ProviderCatalog()
    # Local inference options (no API key required).
    catalog.register(MockProvider(name="mock", model="mock-model"))
    # Register all available real providers (respects environment variables).
    register_all_providers(catalog)
    return catalog
