"""Unit tests for app.domain.tool — safety tiers and approval states."""

from __future__ import annotations

import pytest

from app.domain.tool import ApprovalState, SafetyTier


class TestSafetyTier:
    def test_safe_tier_requires_no_hitl(self):
        assert SafetyTier.SAFE.requires_hitl() is False

    def test_sensitive_tier_requires_no_hitl(self):
        assert SafetyTier.SENSITIVE.requires_hitl() is False

    def test_destructive_tier_requires_hitl(self):
        assert SafetyTier.DESTRUCTIVE.requires_hitl() is True

    def test_safe_auto_approvable_always(self):
        assert SafetyTier.SAFE.auto_approvable() is True
        assert (
            SafetyTier.SAFE.auto_approvable(policy_auto_approve_sensitive=False) is True
        )

    def test_sensitive_auto_approvable_respects_policy(self):
        assert SafetyTier.SENSITIVE.auto_approvable() is True
        assert (
            SafetyTier.SENSITIVE.auto_approvable(policy_auto_approve_sensitive=False)
            is False
        )

    def test_destructive_never_auto_approvable(self):
        assert SafetyTier.DESTRUCTIVE.auto_approvable() is False
        assert (
            SafetyTier.DESTRUCTIVE.auto_approvable(policy_auto_approve_sensitive=True)
            is False
        )

    def test_enum_values(self):
        assert SafetyTier.SAFE.value == "safe"
        assert SafetyTier.SENSITIVE.value == "sensitive"
        assert SafetyTier.DESTRUCTIVE.value == "destructive"


class TestApprovalState:
    def test_enum_values(self):
        assert ApprovalState.PENDING.value == "pending"
        assert ApprovalState.AUTO_APPROVED.value == "auto_approved"
        assert ApprovalState.HITL_REQUIRED.value == "hitl_required"
        assert ApprovalState.HITL_APPROVED.value == "hitl_approved"
        assert ApprovalState.HITL_REJECTED.value == "hitl_rejected"
        assert ApprovalState.EXPIRED.value == "expired"

    def test_all_members_present(self):
        assert {s.value for s in ApprovalState} == {
            "pending",
            "auto_approved",
            "hitl_required",
            "hitl_approved",
            "hitl_rejected",
            "expired",
        }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
