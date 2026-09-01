"""Local Piper TTS provider for PROFESSOR-J voice subsystem."""

from __future__ import annotations

import logging
import os
import tempfile
from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path
from typing import Any

import piper
from piper.voice import PiperVoice

from app.voice.tts.base import SynthesisResult, TTSProvider, VoiceInfo

logger = logging.getLogger(__name__)

# Default voice mappings
DEFAULT_VOICES = {
    "en_US-lessac-medium": VoiceInfo(
        id="en_US-lessac-medium",
        name="Lessac (US English, Medium)",
        language="en_US",
        quality="medium",
        sample_rate=22050,
    ),
    "en_US-amy-medium": VoiceInfo(
        id="en_US-amy-medium",
        name="Amy (US English, Medium)",
        language="en_US",
        quality="medium",
        sample_rate=22050,
    ),
    "en_US-kathleen-medium": VoiceInfo(
        id="en_US-kathleen-medium",
        name="Kathleen (US English, Medium)",
        language="en_US",
        quality="medium",
        sample_rate=22050,
    ),
    "en_GB-alan-medium": VoiceInfo(
        id="en_GB-alan-medium",
        name="Alan (UK English, Medium)",
        language="en_GB",
        quality="medium",
        sample_rate=22050,
    ),
    "en_GB-southern_english_female-medium": VoiceInfo(
        id="en_GB-southern_english_female-medium",
        name="Southern English Female (UK, Medium)",
        language="en_GB",
        quality="medium",
        sample_rate=22050,
    ),
}

HUGGINGFACE_VOICE_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"


class PiperLocalProvider(TTSProvider):
    """Local Piper TTS provider."""

    def __init__(
        self,
        default_voice: str = "en_US-lessac-medium",
        voices_dir: str | Path | None = None,
        use_cuda: bool = False,
    ) -> None:
        """Initialize the Piper local provider.

        Args:
            default_voice: Default voice ID to use
            voices_dir: Directory to cache voice models
            use_cuda: Whether to use CUDA (not recommended for Intel Arc)
        """
        self._default_voice = default_voice
        self._voices_dir = Path(voices_dir) if voices_dir else Path("./piper_voices")
        self._use_cuda = use_cuda
        self._voice_cache: dict[str, PiperVoice] = {}
        self._available_voices: dict[str, VoiceInfo] = {}
        self._warmed_up = False

    @property
    def name(self) -> str:
        return "piper_local"

    @property
    def is_available(self) -> bool:
        return True  # Piper is always available if installed

    def warmup(self) -> None:
        """Load the default voice."""
        if self._warmed_up:
            return

        logger.info(f"Warming up Piper TTS with default voice: {self._default_voice}")
        self._ensure_voice(self._default_voice)
        self._warmed_up = True
        logger.info("Piper TTS ready")

    def _voice_model_path(self, voice_id: str) -> Path:
        return self._voices_dir / f"{voice_id}.onnx"

    def _voice_config_path(self, voice_id: str) -> Path:
        return self._voices_dir / f"{voice_id}.onnx.json"

    def _ensure_voice(self, voice_id: str) -> PiperVoice:
        """Ensure a voice is loaded, downloading if necessary."""
        if voice_id in self._voice_cache:
            return self._voice_cache[voice_id]

        model_path = self._voice_model_path(voice_id)
        config_path = self._voice_config_path(voice_id)

        # Download if not present
        if not model_path.exists() or not config_path.exists():
            self._download_voice(voice_id)

        # Load voice
        voice = PiperVoice.load(
            str(model_path),
            str(config_path),
            use_cuda=self._use_cuda,
        )
        self._voice_cache[voice_id] = voice
        return voice

    def _download_voice(self, voice_id: str) -> None:
        """Download a Piper voice from Hugging Face."""
        import urllib.request

        self._voices_dir.mkdir(parents=True, exist_ok=True)

        # Parse voice_id to construct Hugging Face URL
        # Format: en_US-lessac-medium -> en/en_US/lessac/medium
        parts = voice_id.split("-")
        if len(parts) >= 3:
            lang_code = parts[0]  # en
            region = parts[1]  # US
            voice_name = parts[2]  # lessac
            quality = parts[3] if len(parts) > 3 else "medium"
        else:
            raise ValueError(f"Invalid voice_id format: {voice_id}")

        hf_path = f"{lang_code}/{lang_code}_{region}/{voice_name}/{quality}"
        base_url = f"{HUGGINGFACE_VOICE_BASE}/{hf_path}"

        model_url = f"{base_url}/{voice_id}.onnx"
        config_url = f"{base_url}/{voice_id}.onnx.json"

        # Only allow https downloads (HUGGINGFACE_VOICE_BASE is a fixed https
        # endpoint); reject any other scheme so urlretrieve can't touch file:
        # or custom schemes.
        for url in (model_url, config_url):
            if not url.startswith("https://"):
                raise ValueError(f"Refusing to download voice from non-https URL: {url}")

        model_path = self._voice_model_path(voice_id)
        config_path = self._voice_config_path(voice_id)

        logger.info(f"Downloading voice {voice_id} from {model_url}")

        try:
            urllib.request.urlretrieve(model_url, model_path)
            urllib.request.urlretrieve(config_url, config_path)
            urllib.request.urlretrieve(model_url, model_path)  # nosec B310: scheme validated to https above
            urllib.request.urlretrieve(config_url, config_path)  # nosec B310: scheme validated to https above
            logger.info(f"Voice {voice_id} downloaded successfully")
        except Exception as e:
            logger.error(f"Failed to download voice {voice_id}: {e}")
            # Clean up partial downloads
            if model_path.exists():
                model_path.unlink()
            if config_path.exists():
                config_path.unlink()
            raise

    def synthesize(self, text: str, voice_id: str | None = None, **kwargs: Any) -> SynthesisResult:
        """Synthesize text to speech."""
        voice_id = voice_id or self._default_voice
        voice = self._ensure_voice(voice_id)

        # Create synthesis config
        syn_config = piper.config.SynthesisConfig(
            length_scale=kwargs.get("length_scale", 1.0),
            noise_scale=kwargs.get("noise_scale", 0.667),
            noise_w_scale=kwargs.get("noise_w_scale", 0.8),
        )

        # Synthesize to temporary file using wave module
        import wave

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with wave.open(tmp_path, "wb") as wav_file:
                wav_file.setnchannels(1)  # mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(voice.config.sample_rate)
                voice.synthesize_wav(text, wav_file, syn_config=syn_config, set_wav_format=False)

            with open(tmp_path, "rb") as f:
                audio_data = f.read()

            return SynthesisResult(
                audio_data=audio_data,
                sample_rate=voice.config.sample_rate,
                format="wav",
            )
        finally:
            with suppress(Exception):
                os.unlink(tmp_path)

    def synthesize_stream(
        self, text: str, voice_id: str | None = None, **kwargs: Any
    ) -> Iterable[bytes]:
        """Synthesize text to speech as a stream of audio chunks."""
        voice_id = voice_id or self._default_voice
        voice = self._ensure_voice(voice_id)

        syn_config = piper.config.SynthesisConfig(
            length_scale=kwargs.get("length_scale", 1.0),
            noise_scale=kwargs.get("noise_scale", 0.667),
            noise_w_scale=kwargs.get("noise_w_scale", 0.8),
        )

        yield from voice.synthesize_stream_raw(text, syn_config=syn_config)  # type: ignore[attr-defined]

    def list_voices(self) -> list[VoiceInfo]:
        """List available voices (downloaded + defaults)."""
        voices = list(DEFAULT_VOICES.values())

        # Add any downloaded voices not in defaults
        for model_file in self._voices_dir.glob("*.onnx"):
            voice_id = model_file.stem
            if voice_id not in DEFAULT_VOICES:
                config_file = self._voices_dir / f"{voice_id}.onnx.json"
                if config_file.exists():
                    # Try to parse voice info from config
                    import json

                    with open(config_file) as f:
                        config = json.load(f)
                    voices.append(
                        VoiceInfo(
                            id=voice_id,
                            name=config.get("name", voice_id),
                            language=config.get("language", "unknown"),
                            quality=config.get("quality", "medium"),
                            sample_rate=config.get("audio", {}).get("sample_rate", 22050),
                        )
                    )

        return voices
