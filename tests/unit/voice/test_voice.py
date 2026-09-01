"""Tests for the ``app.voice`` subsystem that run WITHOUT loading real ML models.

The goal of this module is to exercise the parts of the voice subsystem that do
not require ``faster-whisper`` or ``piper`` models to be instantiated: provider
factories, lazy getters in ``routes.py``, the base dataclasses, and the
validation/path-helpers of ``WhisperAPIProvider`` and ``PiperLocalProvider``.

The heavy model constructors (``WhisperModel``, ``PiperVoice.load``) and network
access (``urlretrieve``) are replaced with fakes so the tests are deterministic,
fast, and CI-portable.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.voice.routes import _get_stt_provider, _get_tts_provider, router
from app.voice.stt.base import TranscriptionResult
from app.voice.stt.factory import STTProviderFactory
from app.voice.stt.whisper_local import WhisperAPIProvider, WhisperLocalProvider
from app.voice.tts.base import SynthesisResult, VoiceInfo
from app.voice.tts.factory import TTSProviderFactory
from app.voice.tts.piper_local import PiperLocalProvider

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_factory_registries() -> Iterator[None]:
    """Snapshot and restore the class-level provider registries between tests.

    ``STTProviderFactory._providers`` and ``TTSProviderFactory._providers`` are
    class attributes mutated by ``get_default``/``register``, so test order must
    not leak registered providers into unrelated tests.
    """
    stt_snapshot = dict(STTProviderFactory._providers)
    tts_snapshot = dict(TTSProviderFactory._providers)
    yield
    STTProviderFactory._providers = stt_snapshot
    TTSProviderFactory._providers = tts_snapshot


def _make_stt_stub() -> object:
    """Return a minimal STT provider stub usable by the routes helpers."""

    class _Stt:
        name = "stub_stt"
        is_available = False

    return _Stt()


def _make_tts_stub() -> object:
    """Return a minimal TTS provider stub usable by the routes helpers."""

    class _Tts:
        name = "stub_tts"
        is_available = True

        def list_voices(self) -> list[VoiceInfo]:
            return []

    return _Tts()


# ---------------------------------------------------------------------------
# Base dataclasses (c)
# ---------------------------------------------------------------------------


def test_transcription_result_defaults() -> None:
    """Optional metadata fields default to None and text is preserved."""
    result = TranscriptionResult(text="hello")
    assert result.text == "hello"
    assert result.language is None
    assert result.duration is None
    assert result.confidence is None


def test_transcription_result_full_construction() -> None:
    """All fields can be set explicitly."""
    result = TranscriptionResult(
        text="hello world",
        language="en",
        duration=3.2,
        confidence=0.98,
    )
    assert result.language == "en"
    assert result.duration == 3.2
    assert result.confidence == 0.98


def test_voice_info_to_dict() -> None:
    """VoiceInfo exposes a flat dict representation."""
    info = VoiceInfo(
        id="en_US-lessac-medium",
        name="Lessac (US English, Medium)",
        language="en_US",
        quality="medium",
    )
    assert info.sample_rate == 22050  # dataclass default
    assert info.to_dict() == {
        "id": "en_US-lessac-medium",
        "name": "Lessac (US English, Medium)",
        "language": "en_US",
        "quality": "medium",
        "sample_rate": 22050,
    }


def test_synthesis_result_defaults() -> None:
    """SynthesisResult takes audio_data/sample_rate and defaults the rest."""
    result = SynthesisResult(audio_data=b"\x00\x01", sample_rate=22050)
    assert result.audio_data == b"\x00\x01"
    assert result.sample_rate == 22050
    assert result.format == "wav"
    assert result.duration is None


def test_synthesis_result_full_construction() -> None:
    """All fields can be set explicitly."""
    result = SynthesisResult(
        audio_data=b"abc",
        sample_rate=16000,
        format="mp3",
        duration=1.5,
    )
    assert result.format == "mp3"
    assert result.duration == 1.5


# ---------------------------------------------------------------------------
# STT factory (a)
# ---------------------------------------------------------------------------


def test_stt_factory_create_whisper_local() -> None:
    """create('whisper_local') returns a WhisperLocalProvider (no model load)."""
    provider = STTProviderFactory.create(provider_type="whisper_local")
    assert isinstance(provider, WhisperLocalProvider)
    assert provider.name == "whisper_local_base"
    assert provider.is_available is False


def test_stt_factory_create_whisper_api() -> None:
    """create('whisper_api') returns a WhisperAPIProvider."""
    provider = STTProviderFactory.create(provider_type="whisper_api", api_key="key")
    assert isinstance(provider, WhisperAPIProvider)
    assert provider.name == "whisper_api"


def test_stt_factory_create_unknown_raises_value_error() -> None:
    """An unknown STT provider type raises ValueError."""
    with pytest.raises(ValueError, match="Unknown STT provider type"):
        STTProviderFactory.create(provider_type="bogus")


def test_stt_factory_get_default_builds_and_caches() -> None:
    """get_default() constructs a base Whisper provider and caches it."""
    first = STTProviderFactory.get_default()
    assert isinstance(first, WhisperLocalProvider)
    assert first._model_size == "base"
    assert first._device == "cpu"
    assert first.is_available is False
    assert STTProviderFactory.get_default() is first


def test_stt_factory_register_and_get_roundtrip() -> None:
    """A manually registered provider is returned by get()."""
    provider = WhisperAPIProvider(api_key="k")
    STTProviderFactory.register("api", provider)
    assert STTProviderFactory.get("api") is provider
    assert STTProviderFactory.get("missing") is None


# ---------------------------------------------------------------------------
# TTS factory (a)
# ---------------------------------------------------------------------------


def test_tts_factory_create_piper_local() -> None:
    """create('piper_local') returns a PiperLocalProvider (no model load)."""
    provider = TTSProviderFactory.create(provider_type="piper_local")
    assert isinstance(provider, PiperLocalProvider)
    assert provider.name == "piper_local"
    assert provider.is_available is True


def test_tts_factory_create_unknown_raises_value_error() -> None:
    """An unknown TTS provider type raises ValueError."""
    with pytest.raises(ValueError, match="Unknown TTS provider type"):
        TTSProviderFactory.create(provider_type="bogus")


def test_tts_factory_get_default_builds_and_caches() -> None:
    """get_default() constructs the default Piper provider and caches it."""
    first = TTSProviderFactory.get_default()
    assert isinstance(first, PiperLocalProvider)
    assert first._default_voice == "en_US-lessac-medium"
    assert first.is_available is True
    assert TTSProviderFactory.get_default() is first


def test_tts_factory_register_and_get_roundtrip() -> None:
    """A manually registered provider is returned by get()."""
    provider = PiperLocalProvider(default_voice="en_GB-alan-medium")
    TTSProviderFactory.register("alan", provider)
    assert TTSProviderFactory.get("alan") is provider
    assert TTSProviderFactory.get("missing") is None


# ---------------------------------------------------------------------------
# routes.py lazy getters (b)
# ---------------------------------------------------------------------------


def test_get_stt_provider_lazily_builds_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    """_get_stt_provider builds once and returns the same cached instance."""
    monkeypatch.setattr("app.voice.routes._stt_provider", None)
    monkeypatch.setattr(
        "app.voice.routes.STTProviderFactory.get_default",
        classmethod(lambda cls: _make_stt_stub()),
    )
    first = _get_stt_provider()
    second = _get_stt_provider()
    assert first is second
    assert first.name == "stub_stt"


def test_get_tts_provider_lazily_builds_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    """_get_tts_provider builds once and returns the same cached instance."""
    monkeypatch.setattr("app.voice.routes._tts_provider", None)
    monkeypatch.setattr(
        "app.voice.routes.TTSProviderFactory.get_default",
        classmethod(lambda cls: _make_tts_stub()),
    )
    first = _get_tts_provider()
    second = _get_tts_provider()
    assert first is second
    assert first.name == "stub_tts"


def test_get_stt_provider_returns_existing_global(monkeypatch: pytest.MonkeyPatch) -> None:
    """A pre-set module global is returned without touching the factory."""
    stub = _make_stt_stub()
    monkeypatch.setattr("app.voice.routes._stt_provider", stub)
    monkeypatch.setattr(
        "app.voice.routes.STTProviderFactory.get_default",
        classmethod(lambda cls: (_ for _ in ()).throw(AssertionError("must not build"))),
    )
    assert _get_stt_provider() is stub


# ---------------------------------------------------------------------------
# WhisperLocalProvider validation / warmup (d)
# ---------------------------------------------------------------------------


class _FakeWhisperModel:
    """Minimal stand-in for faster_whisper.WhisperModel."""

    constructed: dict[tuple[object, ...], int] = {}

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.args = args
        self.kwargs = kwargs


class _FakeSegment:
    text = "hello world"


class _FakeInfo:
    language = "en"
    language_probability = 0.95
    duration = 3.2


class _FakeModel:
    """Mocked WhisperModel exposing ``transcribe`` returning fake segments."""

    def transcribe(self, *args: object, **kwargs: object) -> tuple[list[_FakeSegment], _FakeInfo]:
        return [_FakeSegment()], _FakeInfo()


def test_whisper_local_init_defaults() -> None:
    """Default construction stores attrs and reports unavailable until warmup."""
    provider = WhisperLocalProvider()
    assert provider._model_size == "base"
    assert provider._device == "cpu"
    assert provider._compute_type == "int8"
    assert provider._language is None
    assert provider._download_root is None
    assert provider.is_available is False
    assert provider.name == "whisper_local_base"
    assert provider._model is None


def test_whisper_local_init_with_download_root(tmp_path: Path) -> None:
    """A download_root is normalized into a Path."""
    provider = WhisperLocalProvider(download_root=tmp_path, language="es")
    assert provider._download_root == tmp_path
    assert provider._language == "es"
    assert provider._device == "cpu"


def test_whisper_local_warmup_stubbed_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """warmup() loads the model through the stubbed constructor and is idempotent."""
    monkeypatch.setattr("app.voice.stt.whisper_local.WhisperModel", _FakeWhisperModel)
    provider = WhisperLocalProvider(download_root=tmp_path, model_size="small")
    provider.warmup()
    assert provider.is_available is True
    assert isinstance(provider._model, _FakeWhisperModel)
    assert provider._warmed_up is True
    # Second warmup is a no-op (returns early, does not reconstruct the model).
    provider.warmup()
    assert isinstance(provider._model, _FakeWhisperModel)


def test_whisper_local_warmup_raises_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """warmup() re-raises when the model constructor fails."""

    def _explode(*args: object, **kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr("app.voice.stt.whisper_local.WhisperModel", _explode)
    provider = WhisperLocalProvider()
    with pytest.raises(RuntimeError, match="boom"):
        provider.warmup()
    assert provider.is_available is False


def test_whisper_local_transcribe_file_stubbed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """transcribe_file() returns a TranscriptionResult from the stubbed model."""
    monkeypatch.setattr(
        "app.voice.stt.whisper_local.WhisperModel",
        lambda *a, **k: _FakeModel(),
    )
    provider = WhisperLocalProvider(language="en")
    result = provider.transcribe_file(tmp_path / "audio.wav")
    assert isinstance(result, TranscriptionResult)
    assert result.text == "hello world"
    assert result.language == "en"
    assert result.duration == 3.2


def test_whisper_local_transcribe_allows_none_language(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A low-confidence language is dropped in favor of None."""

    class _LowConfidenceInfo:
        language = "xx"
        language_probability = 0.2
        duration = 1.0

    class _Model:
        def transcribe(
            self, *args: object, **kwargs: object
        ) -> tuple[list[_FakeSegment], _LowConfidenceInfo]:
            return [_FakeSegment()], _LowConfidenceInfo()

    monkeypatch.setattr("app.voice.stt.whisper_local.WhisperModel", lambda *a, **k: _Model())
    provider = WhisperLocalProvider()
    result = provider.transcribe_file(tmp_path / "audio.wav")
    assert result.language is None


def test_whisper_local_transcribe_writes_temp_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """transcribe() saves audio to a temp file, delegates, and cleans up."""
    seen_paths: list[Path] = []

    def _fake_whisper(*a: object, **k: object) -> _FakeModel:
        return _FakeModel()

    def _fake_transcribe_file(self: WhisperLocalProvider, audio_path: Path) -> TranscriptionResult:  # noqa: ARG002
        seen_paths.append(audio_path)
        assert audio_path.exists()
        return TranscriptionResult(text="ok", language="en", duration=1.0)

    monkeypatch.setattr("app.voice.stt.whisper_local.WhisperModel", _fake_whisper)
    monkeypatch.setattr(WhisperLocalProvider, "transcribe_file", _fake_transcribe_file)

    provider = WhisperLocalProvider()
    result = provider.transcribe(b"\x00\x01", content_type="audio/webm")
    assert result.text == "ok"
    assert len(seen_paths) == 1
    assert seen_paths[0].suffix == ".webm"
    # Temp file is cleaned up after delegation.
    assert not seen_paths[0].exists()


# ---------------------------------------------------------------------------
# WhisperAPIProvider validation (d)
# ---------------------------------------------------------------------------


def test_whisper_api_init_defaults_and_availability() -> None:
    """is_available reflects whether an API key is configured."""
    provider = WhisperAPIProvider()
    assert provider._api_key is None
    assert provider._model == "whisper-1"
    assert provider.name == "whisper_api"
    assert provider.is_available is False

    with_key = WhisperAPIProvider(api_key="sk-test", model="test-model")
    assert with_key.is_available is True
    assert with_key._model == "test-model"


def test_whisper_api_transcribe_file_raises_without_key(tmp_path: Path) -> None:
    """Without an API key, transcribe_file raises RuntimeError."""
    provider = WhisperAPIProvider()
    with pytest.raises(RuntimeError, match="API key not configured"):
        provider.transcribe_file(tmp_path / "audio.wav")


def test_whisper_api_warmup_stubbed_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    """warmup() builds the OpenAI client via the stubbed import."""
    captured: dict[str, object] = {}

    class _FakeOpenAI:
        def __init__(self, *, api_key: str) -> None:
            captured["api_key"] = api_key

    import builtins

    real_import = builtins.__import__

    def _fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "openai":
            module = type("openai", (), {})()
            module.OpenAI = _FakeOpenAI
            return module
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    provider = WhisperAPIProvider(api_key="sk-test")
    assert provider._client is None
    provider.warmup()
    assert captured["api_key"] == "sk-test"
    assert provider._client is not None
    # Second warmup does not rebuild the client.
    provider.warmup()
    assert captured["api_key"] == "sk-test"


def test_whisper_api_transcribe_file_full_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """transcribe_file() with a working client returns a TranscriptionResult."""

    class _FakeTranscriptions:
        def create(self, **kwargs: object) -> object:
            class _Resp:
                text = "hello"
                language = "en"
                duration = 2.5

            return _Resp()

    class _FakeAudio:
        transcriptions = _FakeTranscriptions()

    class _FakeClient:
        audio = _FakeAudio()

    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"\x00" * 8)

    import builtins

    real_import = builtins.__import__

    def _fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "openai":
            module = type("openai", (), {})()
            module.OpenAI = lambda *, api_key: _FakeClient()
            return module
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    provider = WhisperAPIProvider(api_key="sk-test")
    result = provider.transcribe_file(audio)
    assert result.text == "hello"
    assert result.language == "en"
    assert result.duration == 2.5


# ---------------------------------------------------------------------------
# PiperLocalProvider validation / path helpers (d)
# ---------------------------------------------------------------------------


def test_piper_init_defaults() -> None:
    """Default construction normalizes voices_dir to a Path."""
    provider = PiperLocalProvider()
    assert provider._default_voice == "en_US-lessac-medium"
    assert provider._voices_dir == Path("./piper_voices")
    assert provider._use_cuda is False
    assert provider.name == "piper_local"
    assert provider.is_available is True
    assert provider._warmed_up is False


def test_piper_voice_model_path(tmp_path: Path) -> None:
    """_voice_model_path/_voice_config_path build .onnx/.json paths."""
    provider = PiperLocalProvider(voices_dir=tmp_path)
    assert (
        provider._voice_model_path("en_US-lessac-medium") == tmp_path / "en_US-lessac-medium.onnx"
    )
    assert (
        provider._voice_config_path("en_US-lessac-medium")
        == tmp_path / "en_US-lessac-medium.onnx.json"
    )


def test_piper_download_voice_rejects_non_https(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """_download_voice refuses anything that is not an https:// URL."""
    monkeypatch.setattr(
        "app.voice.tts.piper_local.HUGGINGFACE_VOICE_BASE",
        "file:///tmp/hf",
    )
    provider = PiperLocalProvider(voices_dir=tmp_path)
    with pytest.raises(ValueError, match="non-https URL"):
        provider._download_voice("en_US-lessac-medium")


def test_piper_download_voice_invalid_format(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A voice_id that cannot be parsed into the HF path raises ValueError."""
    monkeypatch.setattr("app.voice.tts.piper_local.HUGGINGFACE_VOICE_BASE", "https://example.com")
    provider = PiperLocalProvider(voices_dir=tmp_path)
    with pytest.raises(ValueError, match="Invalid voice_id format"):
        provider._download_voice("bad")


def test_piper_warmup_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    """warmup() ensures the default voice then is a no-op on second call."""
    calls: list[str] = []

    def _ensure(self: PiperLocalProvider, voice_id: str) -> object:  # noqa: ARG002
        calls.append(voice_id)
        return VoiceInfo(id="v", name="v", language="en", quality="low")

    monkeypatch.setattr(PiperLocalProvider, "_ensure_voice", _ensure)
    provider = PiperLocalProvider()
    provider.warmup()
    provider.warmup()
    assert calls == ["en_US-lessac-medium"]
    assert provider._warmed_up is True


def test_piper_ensure_voice_uses_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """_ensure_voice downloads+loads once and serves the cached voice after."""

    class _FakePiperVoice:
        config = type("Cfg", (), {"sample_rate": 22050})()

    load_calls: list[str] = []

    # Create the onnx model + config files so no download is triggered.
    (tmp_path / "foo.onnx").write_bytes(b"m")
    (tmp_path / "foo.onnx.json").write_text("{}")

    class _FakePiperVoiceModule:
        @staticmethod
        def load(*args: object, **kwargs: object) -> _FakePiperVoice:
            load_calls.append(str(args[0]))
            return _FakePiperVoice()

    monkeypatch.setattr("app.voice.tts.piper_local.PiperVoice", _FakePiperVoiceModule)
    provider = PiperLocalProvider(voices_dir=tmp_path)
    first = provider._ensure_voice("foo")
    second = provider._ensure_voice("foo")
    assert first is second
    assert load_calls == [str(tmp_path / "foo.onnx")]


def test_piper_download_voice_downloads_both_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """_download_voice fetches the .onnx model and .onnx.json config via https."""
    monkeypatch.setattr("app.voice.tts.piper_local.HUGGINGFACE_VOICE_BASE", "https://example.com")

    downloaded: list[str] = []

    class _FakeURL:
        def __init__(self, fetch: object) -> None:
            real = Path(__file__)
            self.fetch = fetch if fetch is not None else real

    # Real urlretrieve would hit the network; substitute it.
    def _fake_urlretrieve(url: str, path: str) -> _FakeURL:
        downloaded.append(url)
        Path(path).write_bytes(b"data")
        return _FakeURL(None)

    monkeypatch.setattr("urllib.request.urlretrieve", _fake_urlretrieve)
    provider = PiperLocalProvider(voices_dir=tmp_path)
    provider._download_voice("en_US-lessac-medium")

    assert (tmp_path / "en_US-lessac-medium.onnx").exists()
    assert (tmp_path / "en_US-lessac-medium.onnx.json").exists()
    assert len(downloaded) == 2
    assert all(url.startswith("https://") for url in downloaded)


def test_piper_download_voice_cleans_up_on_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """_download_voice removes partial files and re-raises on download failure."""

    def _fail(*args: object, **kwargs: object) -> None:
        raise OSError("network down")

    monkeypatch.setattr(
        "app.voice.tts.piper_local.HUGGINGFACE_VOICE_BASE",
        "https://example.com",
    )
    monkeypatch.setattr("urllib.request.urlretrieve", _fail)
    provider = PiperLocalProvider(voices_dir=tmp_path)
    with pytest.raises(OSError, match="network down"):
        provider._download_voice("en_US-lessac-medium")
    # Partial files cleaned up.
    assert not (tmp_path / "en_US-lessac-medium.onnx").exists()
    assert not (tmp_path / "en_US-lessac-medium.onnx.json").exists()


def test_piper_list_voices_includes_defaults(tmp_path: Path) -> None:
    """list_voices() returns the built-in DEFAULT_VOICES catalogue."""
    provider = PiperLocalProvider(voices_dir=tmp_path)
    voices = provider.list_voices()
    assert len(voices) >= 5
    ids = {v.id for v in voices}
    assert "en_US-lessac-medium" in ids
    assert "en_GB-alan-medium" in ids


def test_piper_list_voices_appends_downloaded(tmp_path: Path) -> None:
    """list_voices() appends a custom downloaded voice parsed from its config."""
    (tmp_path / "custom.onnx").write_bytes(b"m")
    (tmp_path / "custom.onnx.json").write_text(
        '{"name": "Custom", "language": "hi_IN", "quality": "high", '
        '"audio": {"sample_rate": 44100}}'
    )
    provider = PiperLocalProvider(voices_dir=tmp_path)
    voices = provider.list_voices()
    custom = [v for v in voices if v.id == "custom"]
    assert len(custom) == 1
    assert custom[0].name == "Custom"
    assert custom[0].language == "hi_IN"
    assert custom[0].quality == "high"
    assert custom[0].sample_rate == 44100


def test_whisper_local_transcribe_ext_branch_content_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """transcribe() picks the temp file extension from the content type."""

    def _fake_whisper(*a: object, **k: object) -> _FakeModel:
        return _FakeModel()

    seen: list[str] = []

    def _fake_tf(self: WhisperLocalProvider, audio_path: Path) -> TranscriptionResult:  # noqa: ARG002
        seen.append(audio_path.suffix)
        return TranscriptionResult(text="ok")

    monkeypatch.setattr("app.voice.stt.whisper_local.WhisperModel", _fake_whisper)
    monkeypatch.setattr(WhisperLocalProvider, "transcribe_file", _fake_tf)
    provider = WhisperLocalProvider()
    provider.transcribe(b"a", content_type="audio/mp4")
    provider.transcribe(b"a", content_type="audio/m4a")
    provider.transcribe(b"a", content_type="audio/ogg")
    assert seen == [".m4a", ".m4a", ".ogg"]


def test_whisper_local_transcribe_file_raises_when_model_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """transcribe_file() raises RuntimeError if the model was never loaded."""
    # Make warmup a no-op so _ensure_model leaves self._model as None.
    monkeypatch.setattr(WhisperLocalProvider, "warmup", lambda self: None)
    provider = WhisperLocalProvider()
    with pytest.raises(RuntimeError, match="model not loaded"):
        provider.transcribe_file(Path("nope.wav"))


# ---------------------------------------------------------------------------
# Routes endpoints (via FastAPI TestClient)
# ---------------------------------------------------------------------------


class _EndpointSTT:
    """Functional STT stub for exercising the /api/voice route handlers."""

    name = "stub_stt"
    is_available = False

    def warmup(self) -> None:
        return None

    def transcribe(self, audio_data: bytes, content_type: str = "audio/wav") -> TranscriptionResult:
        return TranscriptionResult(
            text=f"heard {len(audio_data)} bytes as {content_type}",
            language="en",
            duration=1.5,
            confidence=0.9,
        )


class _EndpointTTS:
    """Functional TTS stub for exercising the /api/voice route handlers."""

    name = "stub_tts"
    is_available = True

    def list_voices(self) -> list[VoiceInfo]:
        return [VoiceInfo(id="v1", name="V1", language="en", quality="low")]

    def synthesize(
        self, text: str, voice_id: str | None = None, **kwargs: object
    ) -> SynthesisResult:
        return SynthesisResult(audio_data=b"\x00\x01" + text.encode(), sample_rate=22050)

    def warmup(self) -> None:
        return None


def _install_route_stubs(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[_EndpointSTT, _EndpointTTS, TestClient]:
    """Reset lazy globals, route the factories to functional stubs and return a client."""
    stt = _EndpointSTT()
    tts = _EndpointTTS()

    class _SttFactory:
        @staticmethod
        def get_default() -> _EndpointSTT:
            return stt

    class _TtsFactory:
        @staticmethod
        def get_default() -> _EndpointTTS:
            return tts

    monkeypatch.setattr("app.voice.routes._stt_provider", None)
    monkeypatch.setattr("app.voice.routes._tts_provider", None)
    monkeypatch.setattr("app.voice.routes.STTProviderFactory", _SttFactory)
    monkeypatch.setattr("app.voice.routes.TTSProviderFactory", _TtsFactory)

    app = FastAPI()
    app.include_router(router)
    return stt, tts, TestClient(app)


def test_voice_status_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/voice/status returns the provider availability snapshot."""
    _, _, client = _install_route_stubs(monkeypatch)
    resp = client.get("/api/voice/status")
    assert resp.status_code == 200
    assert resp.json()["stt"] == {"provider": "stub_stt", "available": False}
    assert resp.json()["tts"]["provider"] == "stub_tts"
    assert resp.json()["tts"]["available"] is True
    assert resp.json()["tts"]["voices"][0]["id"] == "v1"


def test_transcribe_audio_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/voice/stt with an audio file returns the transcription."""
    _, _, client = _install_route_stubs(monkeypatch)
    resp = client.post(
        "/api/voice/stt",
        files={"audio": ("clip.wav", b"\x00\x01", "audio/wav")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["text"].startswith("heard 2 bytes")
    assert body["language"] == "en"
    assert body["duration"] == 1.5
    assert body["confidence"] == 0.9


def test_transcribe_audio_endpoint_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /api/voice/stt returns 500 when the provider raises."""
    stt, _, client = _install_route_stubs(monkeypatch)

    def _boom(
        self: _EndpointSTT, audio_data: bytes, content_type: str = "audio/wav"
    ) -> TranscriptionResult:  # noqa: ARG002
        raise RuntimeError("stt broke")

    monkeypatch.setattr(stt, "transcribe", _boom)
    resp = client.post("/api/voice/stt", files={"audio": ("clip.wav", b"x", "audio/wav")})
    assert resp.status_code == 500
    assert "stt broke" in resp.json()["detail"]


def test_synthesize_speech_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/voice/tts streams synthesized audio back to the client."""
    _, _, client = _install_route_stubs(monkeypatch)
    resp = client.post("/api/voice/tts", data={"text": "hello there"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("audio/wav")
    assert resp.headers["x-sample-rate"] == "22050"
    assert resp.headers["x-duration"] == "unknown"
    assert b"hello there" in resp.content


def test_list_voices_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/voice/voices lists voices and the default voice id."""
    _, _, client = _install_route_stubs(monkeypatch)
    resp = client.get("/api/voice/voices")
    assert resp.status_code == 200
    assert resp.json()["voices"][0]["id"] == "v1"
    assert resp.json()["default"] is None  # stub has no _default_voice attr


def test_warmup_voice_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/voice/warmup warms both providers and reports status."""
    stt, tts, client = _install_route_stubs(monkeypatch)
    warmed: list[str] = []
    monkeypatch.setattr(stt, "warmup", lambda: warmed.append("stt"))
    monkeypatch.setattr(tts, "warmup", lambda: warmed.append("tts"))
    resp = client.post("/api/voice/warmup")
    assert resp.status_code == 200
    assert resp.json()["status"] == "warmed_up"
    assert warmed == ["stt", "tts"]


def test_warmup_voice_endpoint_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/voice/warmup returns 500 when a provider warmup fails."""
    _, tts, client = _install_route_stubs(monkeypatch)
    monkeypatch.setattr(tts, "warmup", lambda: (_ for _ in ()).throw(RuntimeError("no tts")))
    resp = client.post("/api/voice/warmup")
    assert resp.status_code == 500
    assert "no tts" in resp.json()["detail"]
