"""PROFESSOR-J authority package (Phase 2 — grant-checked capability registration + audit).

Provides the registration-policy seam that governs whether a capability (tool/skill) may be
registered (closing the audit gap where `ToolExecutor.register()` / `SkillRegistry.register()`
had no authorization model), and the immutable audit ledger (P9) for consequential actions.
"""

from app.authority.ledger import AuthorityLedger
from app.authority.policy import (
    _BLESSED_REGISTRAR_TIERS,
    RegisterPolicy,
    default_register_policy,
)

__all__ = [
    "AuthorityLedger",
    "RegisterPolicy",
    "default_register_policy",
    "_BLESSED_REGISTRAR_TIERS",
]
