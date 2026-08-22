"""Tool Safety Types — Safety tiers and approval states for tool execution."""

from __future__ import annotations

from enum import Enum


class SafetyTier(str, Enum):
    """
    Tool safety tier — determines approval requirements.

    SAFE: Read-only, no side effects, auto-approved.
    SENSITIVE: May have side effects, policy-verified, auto-approved if policy allows.
    DESTRUCTIVE: Irreversible or dangerous, mandatory Human-in-the-Loop approval.
    """

    SAFE = "safe"
    SENSITIVE = "sensitive"
    DESTRUCTIVE = "destructive"

    def requires_hitl(self) -> bool:
        """Whether this tier requires Human-in-the-Loop approval."""
        return self == SafetyTier.DESTRUCTIVE

    def auto_approvable(self, policy_auto_approve_sensitive: bool = True) -> bool:
        """Whether this tier can be auto-approved under given policy."""
        if self == SafetyTier.SAFE:
            return True
        if self == SafetyTier.SENSITIVE:
            return policy_auto_approve_sensitive
        return False


class ApprovalState(str, Enum):
    """Approval state for a tool call request."""

    PENDING = "pending"  # Awaiting evaluation
    AUTO_APPROVED = "auto_approved"  # Approved by policy (SAFE/SENSITIVE)
    HITL_REQUIRED = "hitl_required"  # DESTRUCTIVE - needs human
    HITL_APPROVED = "hitl_approved"  # Human approved
    HITL_REJECTED = "hitl_rejected"  # Human rejected
    EXPIRED = "expired"  # Approval request timed out
