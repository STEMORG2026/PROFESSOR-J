"""Safety gate policy — the decorator that enforces tiered approval.

Every tool a cognitive agent may invoke must be wrapped with ``@safety_gate``
so that:

* ``SAFE``      — read-only; auto-approved after injection/PII checks.
* ``SENSITIVE`` — side-effect-capable; auto-approved by policy (configurable)
                  after injection/PII checks.
* ``DESTRUCTIVE``— irreversible/dangerous; requires an explicit human
                  approval callback. Without approval it raises
                  :class:`~app.exceptions.HITLRequiredError`.

This is the single choke point referenced by the architecture
(``app/guardrails/``). It must stay ahead of real tool exposure.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from app.domain.tool import SafetyTier
from app.exceptions import HITLRequiredError, SafetyGateError
from app.guardrails.injection import PromptInjectionDetector
from app.guardrails.pii import PIIRedactor

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")

ApprovalCallback = Callable[[str, dict[str, Any], str], bool]


@dataclass(slots=True)
class SafetyPolicy:
    """Approval + sanitization policy for the safety gate."""

    auto_approve_sensitive: bool = True
    injection: PromptInjectionDetector = field(default_factory=PromptInjectionDetector)
    pii: PIIRedactor = field(default_factory=PIIRedactor)
    # Set at runtime by the application root to enable DESTRUCTIVE approval.
    approval_callback: ApprovalCallback | None = None

    def _require_approval(
        self, tool: str, args: dict[str, Any], description: str
    ) -> None:
        if self.approval_callback is None:
            raise HITLRequiredError(tool=tool, description=description)
        approved = self.approval_callback(tool, args, description)
        if not approved:
            raise HITLRequiredError(tool=tool, description=description)

    def check(
        self, tool: str, args: dict[str, Any], tier: SafetyTier, description: str
    ) -> dict[str, Any]:
        """Validate a call; return the PII-sanitized argument copy for logging.

        Raises PromptInjectionError, HITLRequiredError, or SafetyGateError.
        """
        # Prompt-injection guard runs on every tier, including SAFE.
        self.injection.assert_safe(args)

        sanitized, _ = self.pii.redact_deep(args)

        if tier == SafetyTier.SAFE:
            return sanitized

        if tier == SafetyTier.SENSITIVE:
            if not self.auto_approve_sensitive:
                self._require_approval(tool, sanitized, description)
            return sanitized

        if tier == SafetyTier.DESTRUCTIVE:
            self._require_approval(tool, sanitized, description)
            return sanitized

        raise SafetyGateError(tool=tool, tier=tier.value, reason=f"Unknown tier {tier}")


def _log_approved(tool: str, tier: SafetyTier, sanitized_args: dict[str, Any]) -> None:
    logger.info(
        "safety_gate approved: tool=%s tier=%s args=%s",
        tool,
        tier.value,
        sanitized_args,
    )


def safety_gate(
    tier: SafetyTier = SafetyTier.SAFE,
    description: str = "",
    policy: SafetyPolicy | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorate a tool so its execution is gated by the safety policy.

    Usage::

        @safety_gate(tier=SafetyTier.SAFE)
        async def lookup_concept(concept_id: str) -> dict: ...

        @safety_gate(tier=SafetyTier.DESTRUCTIVE, description="Run user code")
        async def run_code(code: str) -> dict: ...
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        tool_name = func.__name__

        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                resolved = _bind_args(func, *args, **kwargs)
                active = policy or _default_policy()
                sanitized = active.check(
                    tool_name, resolved, tier, description or func.__doc__ or ""
                )
                # executed against original args; sanitized copy is only for audit
                _log_approved(tool_name, tier, sanitized)
                return await func(*args, **kwargs)

            return async_wrapper  # type: ignore[return-value]

        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            resolved = _bind_args(func, *args, **kwargs)
            active = policy or _default_policy()
            sanitized = active.check(
                tool_name, resolved, tier, description or func.__doc__ or ""
            )
            _log_approved(tool_name, tier, sanitized)
            return func(*args, **kwargs)

        return sync_wrapper

    return decorator


_default: SafetyPolicy | None = None


def set_default_policy(policy: SafetyPolicy) -> None:
    """Install the process-wide default safety policy (set at app bootstrap)."""
    global _default
    _default = policy


def reset_default_policy() -> None:
    """Clear the process-wide policy (useful in tests)."""
    global _default
    _default = None


def _default_policy() -> SafetyPolicy:
    if _default is not None:
        return _default
    # Fall back to a fresh policy; DESTRUCTIVE will require approval that is
    # unavailable until the app wires the callback, so it fails closed.
    return SafetyPolicy(approval_callback=None)


def _bind_args(func: Callable[..., Any], *args: Any, **kwargs: Any) -> dict[str, Any]:
    """Resolve positional args into a name->value dict using the function's signature."""
    try:
        sig = inspect.signature(func)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        return dict(bound.arguments)
    except (TypeError, ValueError):
        return {**{str(i): v for i, v in enumerate(args)}, **kwargs}


# Re-export the tier enum for callers that only import the gate.
__all__ = [
    "ApprovalCallback",
    "SafetyPolicy",
    "safety_gate",
    "set_default_policy",
    "reset_default_policy",
    "SafetyTier",
]
