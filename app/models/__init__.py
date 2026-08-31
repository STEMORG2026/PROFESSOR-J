"""Model pool — typed providers, catalog, and routing with failover.

Entry points:
- ``LLMProvider`` interface: ``MockProvider`` (tests/dev) and
  ``OpenAICompatProvider`` / ``OpenAICompatibleProvider`` (any OpenAI-compatible endpoint).
- Real providers: ``AnthropicProvider``, ``OllamaProvider``, ``GoogleProvider``,
  ``OpenAICompatibleProvider`` (covers Groq, Together, OpenRouter, etc.).
- ``ProviderCatalog``: curated defaults + dynamic registration.
- ``ModelRouter``: multi-provider failover over circuit breakers.
"""

from app.models.catalog import ProviderCatalog, default_catalog  # noqa: F401
from app.models.providers import (  # noqa: F401
    LLMMessage,
    LLMProvider,
    LLMResult,
    MockProvider,
    OpenAICompatProvider,
)
from app.models.real_providers import (  # noqa: F401
    AnthropicProvider,
    GoogleProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
    register_all_providers,
)
from app.models.retry import bounded_retry  # noqa: F401
from app.models.router import ModelRouter  # noqa: F401

__all__ = [
    "LLMMessage",
    "LLMProvider",
    "LLMResult",
    "MockProvider",
    "OpenAICompatProvider",
    "OpenAICompatibleProvider",
    "AnthropicProvider",
    "OllamaProvider",
    "GoogleProvider",
    "register_all_providers",
    "ProviderCatalog",
    "default_catalog",
    "ModelRouter",
    "bounded_retry",
]
