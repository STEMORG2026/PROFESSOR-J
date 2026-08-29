"""STT Provider abstraction for PROFESSOR-J voice subsystem."""

from __future__ import annotations

import abc
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TranscriptionResult:
    """Result of speech transcription."""

    text: str
    language: str | None = None
    duration: float | None = None
    confidence: float | None = None


class STTProvider(abc.ABC):
    """Abstract base class for Speech-to-Text providers."""

    @abc.abstractmethod
    def transcribe(self, audio_data: bytes, content_type: str = "audio/wav") -> TranscriptionResult:
        """Transcribe audio data to text.

        Args:
            audio_data: Raw audio bytes
            content_type: MIME type of audio data

        Returns:
            TranscriptionResult with text and metadata
        """

    @abc.abstractmethod
    def transcribe_file(self, audio_path: Path) -> TranscriptionResult:
        """Transcribe audio file to text.

        Args:
            audio_path: Path to audio file

        Returns:
            TranscriptionResult with text and metadata
        """

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
        """Warm up the model (load into memory)."""
