"""Voice subsystem initialization."""

from __future__ import annotations

from app.voice.stt.base import STTProvider, TranscriptionResult
from app.voice.stt.factory import STTProviderFactory
from app.voice.stt.whisper_local import WhisperAPIProvider, WhisperLocalProvider
from app.voice.tts.base import SynthesisResult, TTSProvider, VoiceInfo
from app.voice.tts.factory import TTSProviderFactory
from app.voice.tts.piper_local import PiperLocalProvider

__all__ = [
    # STT
    "STTProvider",
    "TranscriptionResult",
    "STTProviderFactory",
    "WhisperLocalProvider",
    "WhisperAPIProvider",
    # TTS
    "TTSProvider",
    "VoiceInfo",
    "SynthesisResult",
    "TTSProviderFactory",
    "PiperLocalProvider",
]
