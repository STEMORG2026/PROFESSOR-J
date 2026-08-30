"""TTS Provider factory for PROFESSOR-J voice subsystem."""

from __future__ import annotations

from typing import Any

from app.voice.tts.base import TTSProvider
from app.voice.tts.piper_local import PiperLocalProvider


class TTSProviderFactory:
    """Factory for creating TTS providers."""

    _providers: dict[str, TTSProvider] = {}

    @classmethod
    def create(cls, provider_type: str, **kwargs: Any) -> TTSProvider:
        """Create a TTS provider instance.

        Args:
            provider_type: Type of provider (piper_local, browser_tts)
            **kwargs: Provider-specific configuration

        Returns:
            TTSProvider instance
        """
        if provider_type == "piper_local":
            return PiperLocalProvider(**kwargs)
        else:
            raise ValueError(f"Unknown TTS provider type: {provider_type}")

    @classmethod
    def get_default(cls) -> TTSProvider:
        """Get the default local Piper provider."""
        if "default" not in cls._providers:
            cls._providers["default"] = PiperLocalProvider(
                default_voice="en_US-lessac-medium",
                voices_dir="./piper_voices",
                use_cuda=False,
            )
        return cls._providers["default"]

    @classmethod
    def register(cls, name: str, provider: TTSProvider) -> None:
        """Register a provider instance."""
        cls._providers[name] = provider

    @classmethod
    def get(cls, name: str) -> TTSProvider | None:
        """Get a registered provider by name."""
        return cls._providers.get(name)
