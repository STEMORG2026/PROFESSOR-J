"""PROFESSOR-J authority package (Phase 2 — grant-checked capability registration).

Provides the registration-policy seam that governs whether a capability (tool/skill) may be
registered, closing the audit gap where `ToolExecutor.register()` / `SkillRegistry.register()`
had no authorization model (audit §G; ADVERSARIAL A1/A5).
"""

from app.authority.policy import (
    _BLESSED_REGISTRAR_TIERS,
    RegisterPolicy,
    default_register_policy,
)

__all__ = [
    "RegisterPolicy",
    "default_register_policy",
    "_BLESSED_REGISTRAR_TIERS",
]
