"""Voice API routes for PROFESSOR-J."""

from __future__ import annotations

import logging
from collections.abc import Generator
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.voice import (
    STTProvider,
    STTProviderFactory,
    SynthesisResult,
    TranscriptionResult,
    TTSProvider,
    TTSProviderFactory,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])

# Provider instances (lazy initialization)
_stt_provider: STTProvider | None = None
_tts_provider: TTSProvider | None = None


def _get_stt_provider() -> STTProvider:
    global _stt_provider
    if _stt_provider is None:
        _stt_provider = STTProviderFactory.get_default()
    return _stt_provider


def _get_tts_provider() -> TTSProvider:
    global _tts_provider
    if _tts_provider is None:
        _tts_provider = TTSProviderFactory.get_default()
    return _tts_provider


@router.get("/status")
async def voice_status() -> dict[str, Any]:
    """Get voice subsystem status."""
    stt = _get_stt_provider()
    tts = _get_tts_provider()

    return {
        "stt": {
            "provider": stt.name,
            "available": stt.is_available,
        },
        "tts": {
            "provider": tts.name,
            "available": tts.is_available,
            "voices": [v.to_dict() for v in tts.list_voices()],
        },
    }


@router.post("/stt")
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: str | None = Form(None),
) -> dict[str, Any]:
    """Transcribe audio to text using STT.

    Args:
        audio: Audio file (wav, webm, mp4, ogg)
        language: Optional language hint (e.g., 'en', 'es')

    Returns:
        Transcription result with text and metadata
    """
    stt = _get_stt_provider()

    # Read audio data
    audio_data = await audio.read()
    content_type = audio.content_type or "audio/wav"

    # If language provided, temporarily override
    original_language = None
    if language and hasattr(stt, "_language"):
        original_language = stt._language
        stt._language = language

    try:
        result: TranscriptionResult = stt.transcribe(audio_data, content_type)
        return {
            "text": result.text,
            "language": result.language,
            "duration": result.duration,
            "confidence": result.confidence,
        }
    except Exception as e:
        logger.error(f"STT failed: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}") from None
    finally:
        if original_language is not None and hasattr(stt, "_language"):
            stt._language = original_language


@router.post("/tts")
async def synthesize_speech(
    text: str = Form(...),
    voice_id: str | None = Form(None),
    length_scale: float = Form(1.0),
    noise_scale: float = Form(0.667),
    noise_w_scale: float = Form(0.8),
) -> StreamingResponse:
    """Synthesize text to speech using TTS.

    Args:
        text: Text to synthesize
        voice_id: Optional voice identifier
        length_scale: Speech rate (1.0 = normal)
        noise_scale: Variation in speech
        noise_w_scale: Variation in phonemes

    Returns:
        Audio stream (WAV format)
    """
    tts = _get_tts_provider()

    try:
        result: SynthesisResult = tts.synthesize(
            text,
            voice_id=voice_id,
            length_scale=length_scale,
            noise_scale=noise_scale,
            noise_w_scale=noise_w_scale,
        )

        # Stream audio response
        def audio_generator() -> Generator[bytes, None, None]:
            yield result.audio_data

        return StreamingResponse(
            audio_generator(),
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=speech.wav",
                "X-Sample-Rate": str(result.sample_rate),
                "X-Duration": str(result.duration) if result.duration else "unknown",
            },
        )
    except Exception as e:
        logger.error(f"TTS failed: {e}")
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {str(e)}") from None


@router.get("/voices")
async def list_voices() -> dict[str, Any]:
    """List available TTS voices."""
    tts = _get_tts_provider()
    voices = tts.list_voices()
    return {
        "voices": [v.to_dict() for v in voices],
        "default": tts._default_voice if hasattr(tts, "_default_voice") else None,
    }


@router.post("/warmup")
async def warmup_voice() -> dict[str, str]:
    """Warm up STT and TTS models (load into memory)."""
    stt = _get_stt_provider()
    tts = _get_tts_provider()

    try:
        stt.warmup()
        tts.warmup()
        return {"status": "warmed_up", "stt": stt.name, "tts": tts.name}
    except Exception as e:
        logger.error(f"Warmup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Warmup failed: {str(e)}") from None
