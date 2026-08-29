"""Tests for app.config.settings — credential resolution.

Covers the workspace practice that the repo-root ``.env`` is the source of truth
for provider credentials. A conflicting shell export (e.g. the global
SINGULARITY_API_KEY in ~/.bashrc meant for other tools) must not override the
repo's own keys.

These tests are deterministic and CI-portable: they stub the repo ``.env`` via
``app.config.settings._repo_env`` with controlled fake values instead of
depending on real secrets that only exist on a developer's machine.
"""

from __future__ import annotations

import pytest

from app.config import settings as settings_module
from app.config.settings import get_settings


def _clear_cache() -> None:
    settings_module.get_settings.cache_clear()


def test_repo_dotenv_key_wins_over_shell_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """A conflicting shell SINGULARITY_API_KEY must not override the repo .env."""
    # The repo .env (stubbed) defines the real key; the ambient shell exports a
    # different one.
    monkeypatch.setattr(
        settings_module,
        "_repo_env",
        lambda: {"SINGULARITY_API_KEY": "sk-REPO-KEY"},
    )
    monkeypatch.setenv("SINGULARITY_API_KEY", "sk-WRO-SHELL-KEY")

    _clear_cache()
    try:
        resolved = get_settings().singularity_api_key
    finally:
        _clear_cache()

    assert resolved == "sk-REPO-KEY"
    assert resolved != "sk-WRO-SHELL-KEY"


def test_provider_keys_resolved_from_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provider keys resolve from the repo .env, taking the repo value."""
    fake_repo_env = {
        "SINGULARITY_API_KEY": "sk-singularity",
        "OPENAI_API_KEY": "sk-openai",
        "OPENROUTER_API_KEY": "sk-openrouter",
        "NVIDIA_NIM_API_KEY": "nv-nim",
        "GOOGLE_API_KEY": "google",
        "GOOGLE_AI_API_KEY": "google-ai",
        "GROQ_API_KEY": "groq",
        "CEREBRAS_API_KEY": "cerebras",
    }
    monkeypatch.setattr(settings_module, "_repo_env", lambda: fake_repo_env)

    _clear_cache()
    try:
        s = get_settings()
    finally:
        _clear_cache()

    assert s.singularity_api_key == "sk-singularity"
    assert s.openai_api_key == "sk-openai"
    assert s.openrouter_api_key == "sk-openrouter"
    assert s.nvidia_nim_api_key == "nv-nim"
    assert s.google_api_key == "google"
    assert s.google_ai_api_key == "google-ai"
    assert s.groq_api_key == "groq"
    assert s.cerebras_api_key == "cerebras"


def test_bare_and_prefixed_env_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both the bare env name and the PROFESSOR_-prefixed variant are accepted."""
    monkeypatch.setenv("PROFESSOR_OPENAI_API_KEY", "sk-prefixed")
    _clear_cache()
    try:
        s = get_settings()
    finally:
        _clear_cache()
    assert s.openai_api_key == "sk-prefixed"


def test_default_base_url_and_provider_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Singularity endpoint defaults are sensible and drive session defaults."""
    from app.adapters.api import DEFAULT_BASE_URL, DEFAULT_MODEL, DEFAULT_PROVIDER

    assert DEFAULT_BASE_URL == "https://api.singularityapi.dev/v1"
    assert DEFAULT_PROVIDER == "singularity"
    assert DEFAULT_MODEL