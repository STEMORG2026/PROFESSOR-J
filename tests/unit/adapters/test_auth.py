"""Tests for the authentication boundary and the egress allow-list.

Added for audit findings S0-1 (no auth on any route) and S0-2 (server credential sent to
a caller-nominated URL). Before this module existed, no test asserted anything about either
control, which is why both were reachable in production.

These tests deliberately cover the *failure* paths as carefully as the success path: a gate
that fails open is indistinguishable from no gate at all, so `test_placeholder_key_*` is as
important as `test_valid_key_*`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.adapters.api import ChatRequest, _make_provider_for, create_app
from app.adapters.auth import _PLACEHOLDER_KEYS, resolve_base_url

# Matches tests/conftest.py and tests/unit/adapters/_auth_helper.py
VALID_KEY = "test-key-not-a-real-credential-2f9c1a"
AUTH = {"Authorization": f"Bearer {VALID_KEY}"}


class TestAuthenticationRequired:
    """Every non-public route must refuse an unauthenticated caller."""

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("post", "/api/chat"),
            ("post", "/api/skills/execute"),
            ("get", "/api/sessions"),
            ("get", "/api/settings"),
            ("post", "/api/upload"),
            ("get", "/api/skills"),
            ("get", "/api/personas"),
        ],
    )
    def test_route_rejects_missing_credentials(self, method: str, path: str) -> None:
        client = TestClient(create_app())
        resp = client.post(path, json={}) if method == "post" else client.get(path)
        assert resp.status_code == 401, (
            f"{method.upper()} {path} returned {resp.status_code} without credentials; "
            "every non-public route must require authentication"
        )

    def test_wrong_token_is_rejected(self) -> None:
        client = TestClient(create_app())
        resp = client.get("/api/sessions", headers={"Authorization": "Bearer not-the-key"})
        assert resp.status_code == 401

    def test_malformed_authorization_header_is_rejected(self) -> None:
        client = TestClient(create_app())
        for header in ("", "Bearer", "Basic abc", "Bearer ", "token-without-scheme"):
            resp = client.get("/api/sessions", headers={"Authorization": header})
            assert resp.status_code == 401, f"accepted malformed header {header!r}"

    def test_x_api_key_header_also_accepted(self) -> None:
        client = TestClient(create_app())
        resp = client.get("/api/sessions", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200

    def test_valid_key_is_accepted(self) -> None:
        client = TestClient(create_app())
        resp = client.get("/api/sessions", headers=AUTH)
        assert resp.status_code == 200


class TestFailsClosed:
    """An unusable configured key must refuse traffic, not admit it."""

    @pytest.mark.parametrize("placeholder", sorted(_PLACEHOLDER_KEYS))
    def test_placeholder_key_refuses_every_request(
        self, placeholder: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PROFESSOR_API_KEY", placeholder)
        from app.config.settings import get_settings

        get_settings.cache_clear()
        try:
            client = TestClient(create_app())
            # Even a request presenting that very placeholder must be refused: it is a
            # publicly known string, so accepting it would be a fake control.
            resp = client.get(
                "/api/sessions",
                headers={"Authorization": f"Bearer {placeholder}"} if placeholder else {},
            )
            assert resp.status_code == 503, (
                f"placeholder key {placeholder!r} produced {resp.status_code}; "
                "an unusable key must fail closed"
            )
        finally:
            get_settings.cache_clear()

    def test_the_declared_default_is_treated_as_a_placeholder(self) -> None:
        """`Settings.api_key` defaults to 'changeme'; it must never be sufficient."""
        assert "changeme" in _PLACEHOLDER_KEYS


class TestPublicSurface:
    """Exactly two endpoints are public. Both are asserted so the surface cannot drift."""

    def test_health_is_public(self) -> None:
        client = TestClient(create_app())
        assert client.get("/api/health").status_code == 200

    def test_voice_status_is_public(self) -> None:
        client = TestClient(create_app())
        assert client.get("/api/voice/status").status_code == 200


class TestNoCredentialGoesToACallerNominatedOrigin:
    """S0-2: the server's own key must never travel to a host the caller picked."""

    def test_base_url_is_not_a_request_field(self) -> None:
        """The vector is gone at the schema level, not merely filtered."""
        assert "base_url" not in ChatRequest.model_fields

    def test_server_key_plus_attacker_origin_is_refused(self) -> None:
        with pytest.raises(HTTPException):
            _make_provider_for(
                provider_id="singularity",
                model="",
                api_key=None,  # falls back to DEFAULT_API_KEY
                base_url="https://attacker.example/v1",
            )

    def test_server_key_plus_attacker_origin_refused_for_every_provider(self) -> None:
        for pid in ("singularity", "openai_compat", "bluesmind", "unknown-provider"):
            with pytest.raises(HTTPException):
                _make_provider_for(
                    provider_id=pid,
                    model="",
                    api_key=None,
                    base_url="https://attacker.example/v1",
                )

    def test_caller_own_key_plus_own_origin_is_still_refused(self) -> None:
        """Refusing is the correct behaviour: origin allow-listing is an operator decision,
        not something a caller can self-authorise by bringing a credential."""
        with pytest.raises(HTTPException):
            _make_provider_for(
                provider_id="openai_compat",
                model="",
                api_key="caller-own-key",
                base_url="https://attacker.example/v1",
            )


class TestResolverAllowsLegitimateOrigins:
    """The control must not break the local-inference path it was designed to permit."""

    @pytest.mark.parametrize(
        "loopback",
        [
            "http://127.0.0.1:11434/v1",
            "http://localhost:8080/v1",
            "http://127.0.0.1:8000",
        ],
    )
    def test_loopback_is_allowed(self, loopback: str) -> None:
        assert resolve_base_url(loopback, "https://default.example/v1") == loopback.rstrip("/")

    def test_absent_candidate_uses_the_server_default(self) -> None:
        assert resolve_base_url(None, "https://default.example/v1") == "https://default.example/v1"

    @pytest.mark.parametrize(
        "bad",
        [
            "not-a-url",
            "ftp://attacker.example/v1",
            "//attacker.example",
            "javascript:alert(1)",
        ],
    )
    def test_malformed_origins_are_refused(self, bad: str) -> None:
        with pytest.raises(HTTPException):
            resolve_base_url(bad, "https://default.example/v1")

    def test_explicit_allowlist_via_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PROFESSOR_ALLOWED_BASE_URLS", "https://vllm.internal.example/v1")
        got = resolve_base_url("https://vllm.internal.example/v1", "https://default.example/v1")
        assert got == "https://vllm.internal.example/v1"

    def test_allowlist_does_not_leak_into_other_origins(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PROFESSOR_ALLOWED_BASE_URLS", "https://vllm.internal.example/v1")
        with pytest.raises(HTTPException):
            resolve_base_url("https://evil.internal.example/v1", "https://default.example/v1")


class TestDestructiveSkillExecutionIsGated:
    """S0-3: an authenticated caller must still not be able to delete files ungated."""

    def test_filesystem_skill_is_classified_destructive(self) -> None:
        from app.domain.tool import SafetyTier
        from app.skills.builtin import register_builtin_skills
        from app.skills.registry import SkillRegistry
        from app.skills.safety import tier_for_skill

        registry = SkillRegistry()
        register_builtin_skills(registry)
        skill = registry.get("filesystem")
        assert skill is not None
        assert tier_for_skill(skill) is SafetyTier.DESTRUCTIVE

    def test_unclassified_skill_defaults_to_destructive(self) -> None:
        """Fail closed: a new skill cannot be silently exposed by omission."""
        from app.domain.tool import SafetyTier
        from app.skills.safety import tier_for_skill

        class _Unclassified:
            class metadata:  # noqa: N801
                name = "brand-new-skill-nobody-classified"

        assert tier_for_skill(_Unclassified()) is SafetyTier.DESTRUCTIVE  # type: ignore[arg-type]

    def test_classification_tables_match_the_real_registry(self) -> None:
        """Every classified name must exist, and every registered skill must be classified.

        This test exists because the first version of `app/skills/safety.py` listed ten
        skill names that do not exist while leaving four real ones to the default. A
        classification table that does not match the registry is worse than none, because
        it reads as coverage.
        """
        from app.skills.builtin import register_builtin_skills
        from app.skills.registry import SkillRegistry
        from app.skills.safety import (
            _DELIBERATELY_UNCLASSIFIED,
            _DESTRUCTIVE_SKILLS,
            _SAFE_SKILLS,
            _SENSITIVE_SKILLS,
        )

        registry = SkillRegistry()
        register_builtin_skills(registry)
        registered = set(registry._skills)

        classified = _SAFE_SKILLS | _SENSITIVE_SKILLS | _DESTRUCTIVE_SKILLS

        unknown = classified - registered
        assert not unknown, (
            f"classification names {sorted(unknown)} are not registered skills — "
            "the table has drifted from the registry"
        )

        unclassified = registered - classified - set(_DELIBERATELY_UNCLASSIFIED)
        assert not unclassified, (
            f"registered skills {sorted(unclassified)} are neither classified nor listed as "
            "deliberately unclassified; add them to app/skills/safety.py"
        )

    def test_no_skill_is_both_safe_and_destructive(self) -> None:
        from app.skills.safety import _DESTRUCTIVE_SKILLS, _SAFE_SKILLS, _SENSITIVE_SKILLS

        assert not (_SAFE_SKILLS & _DESTRUCTIVE_SKILLS)
        assert not (_SAFE_SKILLS & _SENSITIVE_SKILLS)
        assert not (_SENSITIVE_SKILLS & _DESTRUCTIVE_SKILLS)

    def test_delete_is_refused_without_an_approval_channel(self, tmp_path: Path) -> None:
        canary = tmp_path / "canary.txt"
        canary.write_text("must survive\n")

        client = TestClient(create_app())
        resp = client.post(
            "/api/skills/execute",
            json={
                "skill_name": "filesystem",
                "params": {"operation": "delete", "path": str(canary)},
            },
            headers=AUTH,
        )
        assert canary.exists(), "an authenticated caller deleted a file without human approval"
        assert resp.json().get("metadata", {}).get("refused") is True
