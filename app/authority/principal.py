"""Principal identity and trustworthy context propagation.

This module defines the authoritative Principal abstraction and its propagation.
The trust root is the composition root (build_root) which creates Principals
at agent construction time. Agents cannot create Principals; they only receive
them as capabilities.

Security properties:
- Principal is frozen and cannot be modified after creation
- Principal can only be created by the composition root (build_root)
- Principal is propagated via contextvar; agents cannot forge it
- The AuthorityGateway verifies Principal existence but does not create it
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.tool import SafetyTier

# Context variable for Principal propagation through the call stack.
# Only the composition root (build_root) should set this.
_principal_context: contextvars.ContextVar[Principal | None] = contextvars.ContextVar(
    "principal", default=None
)


@dataclass(frozen=True, slots=True)
class Principal:
    """Authenticated principal for authorization decisions.

    Instances can only be created by the composition root via Principal.create().
    The constructor is private to prevent forgery by agents or untrusted code.
    """

    id: str  # Unique agent identifier (e.g., "researcher", "implementer")
    tier: SafetyTier  # Maximum authority tier this principal may exercise
    project: str  # Project this principal operates within (e.g., "PROFESSOR-J")
    allocation_ref: str  # Reference to allocation.yaml entry (e.g., "PROFESSOR-J")

    # Private constructor marker - only create() should instantiate
    _trusted: bool = False

    @classmethod
    def create(
        cls,
        id: str,
        tier: SafetyTier,
        project: str,
        allocation_ref: str,
    ) -> Principal:
        """Create a new Principal. Only the composition root should call this."""
        return cls(
            id=id,
            tier=tier,
            project=project,
            allocation_ref=allocation_ref,
            _trusted=True,
        )

    def __post_init__(self) -> None:
        if not self._trusted:
            raise RuntimeError(
                "Principal.forge_attempt: Principal constructor is private. "
                "Use Principal.create() from the composition root only."
            )

    def can_execute_tier(self, required_tier: SafetyTier) -> bool:
        """Check if this principal's tier permits the required tier."""
        from app.domain.tool import SafetyTier

        tier_order = {
            SafetyTier.SAFE: 0,
            SafetyTier.SENSITIVE: 1,
            SafetyTier.DESTRUCTIVE: 2,
        }
        return tier_order[self.tier] >= tier_order[required_tier]


def get_current_principal() -> Principal | None:
    """Get the current principal from context. Returns None if not set."""
    return _principal_context.get()


def set_current_principal(principal: Principal | None) -> contextvars.Token[Principal | None]:
    """Set the current principal in context. Returns a token for restoration."""
    return _principal_context.set(principal)


def reset_current_principal(token: contextvars.Token[Principal | None]) -> None:
    """Reset the principal context to a previous state."""
    _principal_context.reset(token)


def require_principal() -> Principal:
    """Get the current principal or raise if none is set."""
    principal = get_current_principal()
    if principal is None:
        raise RuntimeError(
            "No principal in context. Privileged operations require an authenticated principal. "
            "Ensure the caller was created by the composition root with a Principal."
        )
    return principal
