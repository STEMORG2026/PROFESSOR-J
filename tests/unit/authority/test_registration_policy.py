"""Tests for the Phase-2 grant-checked capability registration policy.

Covers: default_register_policy tier rules, ToolExecutor registration gating
(blessed vs non-blessed registrar), and SkillRegistry no-silent-overwrite + policy
denial. Closes the authority-audit gap (unpermissioned capability registration,
audit §G; ADVERSARIAL A1/A5).
"""

from __future__ import annotations

from typing import Any

import pytest

from app.authority.policy import default_register_policy
from app.domain.tool import SafetyTier
from app.exceptions import CapabilityRegistrationError
from app.skills.base import Skill, SkillMetadata
from app.skills.registry import SkillRegistry
from app.tools.executor import ToolExecutor
from app.tools.sandbox import CodeSandbox

# ── default_register_policy ─────────────────────────────────────────


class TestDefaultRegisterPolicy:
    def test_non_blessed_allows_safe_and_sensitive(self) -> None:
        for tier in (SafetyTier.SAFE, SafetyTier.SENSITIVE):
            assert default_register_policy("tool", tier, blessed=False) is True

    def test_non_blessed_denies_destructive(self) -> None:
        # An agent/skill cannot self-grant DESTRUCTIVE authority.
        assert default_register_policy("tool", SafetyTier.DESTRUCTIVE, blessed=False) is False

    def test_blessed_allows_destructive(self) -> None:
        # The composition root may provision the full toolset incl. DESTRUCTIVE.
        assert default_register_policy("tool", SafetyTier.DESTRUCTIVE, blessed=True) is True


# ── ToolExecutor registration gating ────────────────────────────────


class TestToolExecutorRegistrationPolicy:
    def test_non_blessed_denies_destructive_tool(self) -> None:
        executor = ToolExecutor(register_policy=default_register_policy, blessed_registrar=False)
        with pytest.raises(CapabilityRegistrationError):
            executor.register_fn(
                "run_code", lambda: None, tier=SafetyTier.DESTRUCTIVE, description="x"
            )

    def test_non_blessed_allows_safe_tool(self) -> None:
        executor = ToolExecutor(register_policy=default_register_policy, blessed_registrar=False)
        executor.register_fn("solve", lambda: 1, tier=SafetyTier.SAFE, description="x")
        assert executor.has_tool("solve")

    def test_blessed_registrar_allows_destructive_tool(self) -> None:
        executor = ToolExecutor(register_policy=default_register_policy, blessed_registrar=True)
        executor.register_fn("run_code", lambda: None, tier=SafetyTier.DESTRUCTIVE, description="x")
        assert executor.has_tool("run_code")

    def test_no_policy_is_backward_compatible(self) -> None:
        # No policy wired => registration behaves exactly as before (permissive).
        executor = ToolExecutor()
        executor.register_fn("anything", lambda: None, tier=SafetyTier.DESTRUCTIVE, description="x")
        assert executor.has_tool("anything")


# ── SkillRegistry no-silent-overwrite + policy ──────────────────────


class _DummySkill(Skill[Any]):
    def __init__(self, name: str = "dummy") -> None:
        super().__init__(metadata=SkillMetadata(name=name, description="d"))

    def _default_metadata(self) -> SkillMetadata:
        return SkillMetadata(name="dummy", description="d")

    async def execute(self, **kwargs: Any) -> Any:  # pragma: no cover
        return None


class TestSkillRegistryPolicy:
    def test_no_silent_overwrite_raises(self) -> None:
        reg = SkillRegistry()
        reg.register(_DummySkill("a"))
        with pytest.raises(CapabilityRegistrationError):
            reg.register(_DummySkill("a"))  # same name, overwrite not set
        assert reg.get("a") is not None

    def test_overwrite_true_replaces(self) -> None:
        reg = SkillRegistry()
        reg.register(_DummySkill("a"))
        reg.register(_DummySkill("a"), overwrite=True)  # no raise
        assert reg.get("a") is not None

    def test_registration_policy_denial(self) -> None:
        reg = SkillRegistry(register_policy=lambda name, cat: name != "blocked")
        reg.register(_DummySkill("ok"))
        with pytest.raises(CapabilityRegistrationError):
            reg.register(_DummySkill("blocked"))
        assert reg.get("blocked") is None


# ── Integration: bootstrap's blessed registrar can provision sandbox ─


class TestBootstrapProvisioning:
    def test_blessed_registrar_can_provision_destructive_sandbox(self) -> None:
        # Mirrors bootstrap.py: blessed registrar + full registration set.
        executor = ToolExecutor(register_policy=default_register_policy, blessed_registrar=True)
        executor.register_sandbox_tools(CodeSandbox())
        assert executor.has_tool("run_code")
        assert executor.has_tool("solve_math")
