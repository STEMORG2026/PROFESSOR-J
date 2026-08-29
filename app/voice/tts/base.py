"""TTS Provider abstraction for PROFESSOR-J voice subsystem."""

from __future__ import annotations

import abc
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


@dataclass
class VoiceInfo:
    """Information about a TTS voice."""

    id: str
    name: str
    language: str
    quality: str  # low, medium, high
    sample_rate: int = 22050

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "language": self.language,
            "quality": self.quality,
            "sample_rate": self.sample_rate,
        }


@dataclass
class SynthesisResult:
    """Result of text-to-speech synthesis."""

    audio_data: bytes
    sample_rate: int
    format: str = "wav"
    duration: float | None = None


class TTSProvider(abc.ABC):
    """Abstract base class for Text-to-Speech providers."""

    @abc.abstractmethod
    def synthesize(self, text: str, voice_id: str | None = None, **kwargs: Any) -> SynthesisResult:
        """Synthesize text to speech.

        Args:
            text: Text to synthesize
            voice_id: Optional voice identifier
            **kwargs: Provider-specific options (rate, pitch, volume, etc.)

        Returns:
            SynthesisResult with audio data and metadata
        """

    @abc.abstractmethod
    def synthesize_stream(
        self, text: str, voice_id: str | None = None, **kwargs: Any
    ) -> Iterable[bytes]:
        """Synthesize text to speech as a stream of audio chunks.

        Args:
            text: Text to synthesize
            voice_id: Optional voice identifier
            **kwargs: Provider-specific options

        Yields:
            Audio chunks as bytes
        """

    @abc.abstractmethod
    def list_voices(self) -> list[VoiceInfo]:
        """List available voices."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Provider identifier."""

    @property
    @abc.abstractmethod
    def is_available(self) -> bool:
        """Check if provider is ready to use."""

    @abc.abstractmethod
    def warmup(self) -> None:
        """Warm up the provider (load models)."""
