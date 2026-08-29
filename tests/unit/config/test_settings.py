"""Tests for app.config.settings — credential resolution.

Covers the workspace practice that the repo ``.env`` is the source of truth
for provider credentials, and must not be shadowed by an unrelated shell
export (e.g. the global SINGULARITY_API_KEY in ~/.bashrc meant for other
tools), which used to break every provider call with a 401.
"""

from __future__ import annotations

import pytest

from app.config import settings as settings_module
from app.config.settings import get_settings


def test_repo_dotenv_key_wins_over_shell_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """A conflicting shell SINGULARITY_API_KEY must not override the repo .env."""
    monkeypatch.setenv("SINGULARITY_API_KEY", "sk-WRONG-SHELL-KEY")
    settings_module.get_settings.cache_clear()
    try:
        resolved = get_settings().singularity_api_key or ""
    finally:
        settings_module.get_settings.cache_clear()

    assert resolved != "sk-WRONG-SHELL-KEY"
    assert resolved and resolved.startswith("sk-")


def test_provider_keys_resolved_from_dotenv() -> None:
    """Provider keys migrated from JARVIS resolve from the repo .env."""
    settings_module.get_settings.cache_clear()
    try:
        s = get_settings()
    finally:
        settings_module.get_settings.cache_clear()
    assert bool(s.singularity_api_key)
    assert bool(s.openrouter_api_key)
    assert bool(s.nvidia_nim_api_key)
    assert bool(s.google_api_key)
    assert bool(s.groq_api_key)
    assert bool(s.cerebras_api_key)
