"""PROFESSOR-J capability-registration policy (Phase 2 — grant-checked registration).

Closes the authority-audit finding that ToolExecutor.register()/SkillRegistry.register()
had no authorization model (audit §G, ADVERSARIAL A1/A5 / "unpermissioned registration,
self-declared tiers").

Design: the registries gain an optional `register_policy` callable. When provided, it is
consulted before a capability (tool or skill) is registered and may deny it. This module
provides the default policy: an agent/skill may NOT self-register DESTRUCTIVE capabilities,
and may only register within a blessed tier allowlist. Backward-compatible: if no policy is
wired, registration behaves exactly as before.
"""

from __future__ import annotations

from collections.abc import Callable

from app.domain.tool import SafetyTier

# A registrar may only introduce a capability whose tier is within this set, unless the
# caller is a blessed bootstrap path (bootstrapping here means registering with an explicit
# `blessed=True`, which only the composition root passes). Values are SafetyTier string values.
_BLESSED_REGISTRAR_TIERS: frozenset[str] = frozenset(
    [SafetyTier.SAFE.value, SafetyTier.SENSITIVE.value]
)

RegisterPolicy = Callable[[str, SafetyTier, bool], bool]
"""Callable(registry_kind, tier, blessed) -> bool. True = allow registration."""


def default_register_policy(kind: str, tier: SafetyTier, blessed: bool = False) -> bool:
    """Allow registration iff the tier is blessed for a non-blessed registrar.

    A `blessed=True` registrar (the composition root provisioning the standard toolset) may
    register any tier, including DESTRUCTIVE. Any other registrar is limited to SAFE/SENSITIVE:
    DESTRUCTIVE self-registration is denied — an agent/skill cannot grant itself the authority
    to run untrusted code without going through the blessed bootstrap path (which itself is
    gated by the safety gate at call time).
    """
    if blessed:
        return True
    return tier.value in _BLESSED_REGISTRAR_TIERS


__all__ = ["default_register_policy", "RegisterPolicy", "_BLESSED_REGISTRAR_TIERS"]
