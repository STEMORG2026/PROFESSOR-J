"""Local Whisper STT provider using faster-whisper."""

from __future__ import annotations

import logging
from contextlib import suppress
from pathlib import Path
from typing import Any

from faster_whisper import WhisperModel  # type: ignore[import-untyped]

from app.voice.stt.base import STTProvider, TranscriptionResult

logger = logging.getLogger(__name__)


class WhisperLocalProvider(STTProvider):
    """Local Whisper STT provider using faster-whisper (CTranslate2)."""

    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        download_root: str | Path | None = None,
        language: str | None = None,
    ) -> None:
        """Initialize the Whisper local provider.

        Args:
            model_size: Whisper model size (tiny, base, small, medium, large)
            device: Device to run on (cpu, cuda)
            compute_type: Quantization type (int8, int8_float16, float16, float32)
            download_root: Directory to cache models
            language: Optional fixed language (None for auto-detect)
        """
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._download_root = Path(download_root) if download_root else None
        self._language = language
        self._model: WhisperModel | None = None
        self._warmed_up = False

    @property
    def name(self) -> str:
        return f"whisper_local_{self._model_size}"

    @property
    def is_available(self) -> bool:
        return self._model is not None

    def warmup(self) -> None:
        """Load the Whisper model into memory."""
        if self._warmed_up:
            return

        logger.info(
            f"Loading Whisper model: {self._model_size} on "
            f"{self._device} ({self._compute_type})"
        )

        try:
            self._model = WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
                download_root=str(self._download_root) if self._download_root else None,
            )
            self._warmed_up = True
            logger.info("Whisper model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise

    def _ensure_model(self) -> None:
        """Ensure model is loaded."""
        if not self._warmed_up:
            self.warmup()

    def transcribe(self, audio_data: bytes, content_type: str = "audio/wav") -> TranscriptionResult:
        """Transcribe audio data to text."""
        self._ensure_model()

        # Save audio data to temporary file for faster-whisper
        import os
        import tempfile

        # Determine file extension from content type
        ext = ".wav"
        if "webm" in content_type:
            ext = ".webm"
        elif "mp4" in content_type or "m4a" in content_type:
            ext = ".m4a"
        elif "ogg" in content_type:
            ext = ".ogg"

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name

        try:
            result = self.transcribe_file(Path(tmp_path))
            return result
        finally:
            with suppress(Exception):
                os.unlink(tmp_path)

    def transcribe_file(self, audio_path: Path) -> TranscriptionResult:
        """Transcribe audio file to text."""
        self._ensure_model()

        if self._model is None:
            raise RuntimeError("Whisper model not loaded")

        try:
            segments, info = self._model.transcribe(
                str(audio_path),
                language=self._language,
                beam_size=5,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500},
            )

            text = " ".join(seg.text for seg in segments).strip()

            return TranscriptionResult(
                text=text,
                language=info.language if info.language_probability > 0.5 else None,
                duration=info.duration,
            )

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise


class WhisperAPIProvider(STTProvider):
    """OpenAI Whisper API provider (cloud fallback)."""

    def __init__(self, api_key: str | None = None, model: str = "whisper-1") -> None:
        self._api_key = api_key
        self._model = model
        self._client: Any = None

    @property
    def name(self) -> str:
        return "whisper_api"

    @property
    def is_available(self) -> bool:
        return self._api_key is not None

    def warmup(self) -> None:
        if self._api_key and self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=self._api_key)

    def transcribe(self, audio_data: bytes, content_type: str = "audio/wav") -> TranscriptionResult:
        import os
        import tempfile

        ext = ".wav"
        if "webm" in content_type:
            ext = ".webm"
        elif "mp4" in content_type or "m4a" in content_type:
            ext = ".m4a"

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name

        try:
            return self.transcribe_file(Path(tmp_path))
        finally:
            with suppress(Exception):
                os.unlink(tmp_path)

    def transcribe_file(self, audio_path: Path) -> TranscriptionResult:
        if not self.is_available:
            raise RuntimeError("OpenAI API key not configured")

        self.warmup()

        with open(audio_path, "rb") as f:
            response = self._client.audio.transcriptions.create(
                model=self._model,
                file=f,
                response_format="verbose_json",
            )

        return TranscriptionResult(
            text=response.text,
            language=response.language,
            duration=response.duration,
        )
