"""STT Provider factory for PROFESSOR-J voice subsystem."""

from __future__ import annotations

from typing import Any

from app.voice.stt.base import STTProvider
from app.voice.stt.whisper_local import WhisperAPIProvider, WhisperLocalProvider


class STTProviderFactory:
    """Factory for creating STT providers."""

    _providers: dict[str, STTProvider] = {}

    @classmethod
    def create(cls, provider_type: str, **kwargs: Any) -> STTProvider:
        """Create an STT provider instance.

        Args:
            provider_type: Type of provider (whisper_local, whisper_api)
            **kwargs: Provider-specific configuration

        Returns:
            STTProvider instance
        """
        if provider_type == "whisper_local":
            return WhisperLocalProvider(**kwargs)
        elif provider_type == "whisper_api":
            return WhisperAPIProvider(**kwargs)
        else:
            raise ValueError(f"Unknown STT provider type: {provider_type}")

    @classmethod
    def get_default(cls) -> STTProvider:
        """Get the default local Whisper provider."""
        if "default" not in cls._providers:
            cls._providers["default"] = WhisperLocalProvider(
                model_size="base",
                device="cpu",
                compute_type="int8",
            )
        return cls._providers["default"]

    @classmethod
    def register(cls, name: str, provider: STTProvider) -> None:
        """Register a provider instance."""
        cls._providers[name] = provider

    @classmethod
    def get(cls, name: str) -> STTProvider | None:
        """Get a registered provider by name."""
        return cls._providers.get(name)
