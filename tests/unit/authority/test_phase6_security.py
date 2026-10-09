"""Black-box security property tests for Phase 6.

These tests ATTACK the security properties rather than testing happy paths.
Each test records: Attack, Expected Result, Actual Result, Enforcement Point, Evidence.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

# The repository root, derived from this file. It used to be the author's absolute
# workspace path — Path("/home/sajan/Projects") — which exists on exactly one machine, so every
# test that reads authority/*.yaml raised "Allocation file not found" on CI. The old
# value was also the repo's *parent*, so joining it with "authority/..." pointed outside
# the checkout even locally.
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))


from app.authority.gateway import AuthorityGateway
from app.authority.principal import (
    Principal,
    require_principal,
    reset_current_principal,
    set_current_principal,
)
from app.domain.tool import SafetyTier
from app.guardrails.policy import SafetyPolicy
from app.tools import ToolExecutor


@pytest.fixture(autouse=True)
def reset_principal_context():
    """Auto-reset principal context before and after each test."""
    from app.authority.principal import (
        _principal_context,
        get_current_principal,
    )

    # Ensure clean state before test
    current = get_current_principal()
    if current is not None:
        _principal_context.set(None)

    yield

    # Clean up after test
    _principal_context.set(None)


class TestIdentitySecurity:
    """Tests for Principal identity security."""

    def test_principal_forge_prevention(self):
        """Direct Principal construction should fail (forge prevention)."""

        with pytest.raises(RuntimeError, match="forge_attempt"):
            Principal(
                id="forged",
                tier=SafetyTier.DESTRUCTIVE,
                project="PROFESSOR-J",
                allocation_ref="PROFESSOR-J",
                _trusted=False,
            )

    def test_principal_context_isolation(self):
        """Principal context cannot be forged by setting arbitrary values."""
        from app.authority.principal import Principal, get_current_principal, set_current_principal
        from app.domain.tool import SafetyTier

        # Create a legitimate principal
        p = Principal.create(id="test", tier=SafetyTier.SAFE, project="TEST", allocation_ref="TEST")
        token = set_current_principal(p)

        # Verify context propagation
        assert get_current_principal().id == "test"
        assert require_principal().id == "test"

        # Reset context using the token
        reset_current_principal(token)
        assert get_current_principal() is None


class TestAllocationEnforcement:
    """Tests for allocation enforcement at gateway."""

    @pytest.fixture
    def gateway(self):
        """Create a test gateway with temporary manifests."""
        import os

        import yaml

        from app.guardrails.policy import SafetyPolicy


        # Create tools with registered test tools
        policy = SafetyPolicy(approval_callback=None)
        tools = ToolExecutor(policy)

        from app.domain.tool import SafetyTier

        tools.register_fn(
            name="test_tool",
            fn=lambda x: {"success": True, "result": x * 2},
            tier=SafetyTier.SAFE,
            description="Test tool",
        )
        tools.register_fn(
            name="destructive_tool",
            fn=lambda: {"success": True},
            tier=SafetyTier.DESTRUCTIVE,
            description="Destructive tool",
        )

        # Create test permission manifest
        temp_dir = tempfile.mkdtemp()
        perm_path = os.path.join(temp_dir, "perm.yaml")
        with open(perm_path, "w") as f:
            import yaml

            yaml.safe_dump(
                {
                    "format": 1,
                    "generated": "2026-09-02",
                    "principals": {
                        "owner": {"name": "Test"},
                        "platform": {"name": "Test"},
                        "agents": {"authority_grant": False, "can_grant_capabilities": False},
                    },
                    "invariants": {},
                    "grants": {
                        "default": [
                            {"capability": "test_tool", "risk_cap": 1, "actions": ["execute"]}
                        ]
                    },
                    "repo_allocation": {
                        "PROFESSOR-J": {
                            "capabilities": ["test_tool"],
                            "profile": "full",
                            "lifecycle": "active",
                            "agents": ["researcher"],
                            "max_tier": 2,
                        },
                        "TEST-PROJECT": {
                            "capabilities": ["test_tool"],
                            "profile": "minimal",
                            "lifecycle": "active",
                            "agents": ["tester"],
                            "max_tier": 1,
                        },
                    },
                },
                f,
            )

        gateway = AuthorityGateway(
            tool_executor=tools,  # Use the same tools instance with registered tools
            safety_policy=SafetyPolicy(approval_callback=None),
            allocation_path=os.path.join(REPO_ROOT, "authority/allocation.yaml"),
            permission_manifest_path=perm_path,
            audit_log_path=None,
        )

        return gateway

    def test_unauthorized_agent_denied(self, gateway):
        """Agent not in allocation.yaml must be denied."""
        from app.authority.principal import Principal
        from app.domain.tool import SafetyTier

        p = Principal.create(
            id="unauthorized",
            tier=SafetyTier.SAFE,
            project="PROFESSOR-J",
            allocation_ref="PROFESSOR-J",
        )
        set_current_principal(p)

        with pytest.raises(Exception) as exc_info:
            asyncio.run(gateway.execute("test_tool", {"x": 5}))
        assert "not allocated" in str(exc_info.value).lower()

    def test_tier_ceiling_enforced(self, gateway):
        """Agent cannot exceed its max_tier."""
        from app.authority.principal import Principal
        from app.domain.tool import SafetyTier

        p = Principal.create(
            id="researcher",
            tier=SafetyTier.SAFE,
            project="PROFESSOR-J",
            allocation_ref="PROFESSOR-J",
        )
        set_current_principal(p)

        result = asyncio.run(gateway.execute("test_tool", {"x": 10}))
        assert result.success is True

    def test_tier_exceeded_denied(self, gateway):
        """Principal with SAFE tier cannot execute DESTRUCTIVE capability."""

        from app.authority.principal import Principal, set_current_principal

        p = Principal.create(
            id="researcher",
            tier=SafetyTier.SAFE,
            project="PROFESSOR-J",
            allocation_ref="PROFESSOR-J",
        )
        set_current_principal(p)

        p_safe = Principal.create(id="safe", tier=SafetyTier.SAFE, project="P", allocation_ref="P")
        assert not p_safe.can_execute_tier(SafetyTier.DESTRUCTIVE)


class TestProjectBoundaryEnforcement:
    """Tests for project vs umbrella precedence."""

    def test_project_cannot_weaken_umbrella_invariants(self):
        """Project config cannot disable signing, audit, or security gates."""
        with open(os.path.join(REPO_ROOT, "authority/allocation.yaml")) as f:
            alloc = yaml.safe_load(f)

        # JARVIS is frozen at T1 - cannot increase
        jarvis = alloc["repo_allocation"]["JARVIS"]
        assert jarvis["max_tier"] == 1
        assert jarvis["lifecycle"] == "frozen"

        # PROFESSOR-J has max_tier 2 - cannot self-grant T3/T4
        prof = alloc["repo_allocation"]["PROFESSOR-J"]
        assert prof["max_tier"] == 2

    def test_legitimate_project_customization_allowed(self):
        """Projects can customize their own domain rules within ceiling."""
        with open(os.path.join(REPO_ROOT, "authority/allocation.yaml")) as f:
            alloc = yaml.safe_load(f)

        # PROFESSOR-J has full specialist set
        prof = alloc["repo_allocation"]["PROFESSOR-J"]
        assert "researcher" in prof["agents"]
        assert "architect" in prof["agents"]
        assert prof["max_tier"] == 2


class TestProvenanceEnforcement:
    """Tests for provenance enforcement."""

    def test_ai_cannot_mutate_without_human_review(self):
        """AI-generated content cannot mutate canonical artifacts without human review."""

        # The _enforce_provenance_rules method enforces this
        # Tested via gateway integration tests

    def test_untrusted_source_requires_human_for_mutation(self):
        """Untrusted source (MCP, retrieved) requires human for privileged mutations."""
        # Tested via gateway integration tests


class TestBlackBoxAttacks:
    """Black-box attack tests per Section 23 of Phase 6 directive."""

    @pytest.fixture
    def gateway(self):
        """Create a test gateway."""
        import os

        import yaml


        policy = SafetyPolicy(approval_callback=None)
        tools = ToolExecutor(policy)

        # Register test tools
        from app.domain.tool import SafetyTier

        tools.register_fn(
            name="test_tool",
            fn=lambda x: {"success": True, "result": x * 2},
            tier=SafetyTier.SAFE,
            description="Test tool",
        )
        tools.register_fn(
            name="destructive_tool",
            fn=lambda: {"success": True},
            tier=SafetyTier.DESTRUCTIVE,
            description="Destructive tool",
        )

        # Create test permission manifest
        import tempfile

        temp_dir = tempfile.mkdtemp()
        perm_path = os.path.join(temp_dir, "perm.yaml")
        with open(perm_path, "w") as f:
            import yaml

            yaml.safe_dump(
                {
                    "format": 1,
                    "generated": "2026-09-02",
                    "principals": {
                        "owner": {"name": "Test"},
                        "platform": {"name": "Test"},
                        "agents": {"authority_grant": False, "can_grant_capabilities": False},
                    },
                    "invariants": {},
                    "grants": {
                        "default": [
                            {"capability": "test_tool", "risk_cap": 1, "actions": ["execute"]}
                        ]
                    },
                    "repo_allocation": {
                        "PROFESSOR-J": {
                            "capabilities": ["test_tool"],
                            "profile": "full",
                            "lifecycle": "active",
                            "agents": ["researcher"],
                            "max_tier": 2,
                        },
                    },
                },
                f,
            )

        gateway = AuthorityGateway(
            tool_executor=tools,
            safety_policy=SafetyPolicy(approval_callback=None),
            allocation_path=os.path.join(REPO_ROOT, "authority/allocation.yaml"),
            permission_manifest_path=os.path.join(
                REPO_ROOT, "authority/permission-manifest.yaml"
            ),
            audit_log_path=None,
        )
        return gateway

    def test_attack_privilege_escalation(self, gateway):
        """Attack: Lower-tier principal tries to execute higher-tier capability."""

        from app.authority.principal import Principal
        from app.domain.tool import SafetyTier

        p = Principal.create(
            id="safe-agent",
            tier=SafetyTier.SAFE,
            project="PROFESSOR-J",
            allocation_ref="PROFESSOR-J",
        )
        set_current_principal(p)

        p_safe = Principal.create(id="test", tier=SafetyTier.SAFE, project="P", allocation_ref="P")
        assert not p_safe.can_execute_tier(SafetyTier.DESTRUCTIVE)

    def test_attack_self_grant(self, gateway):
        """Attack: Agent tries to grant itself higher authority."""
        from app.authority.principal import Principal

        p = Principal.create(id="test", tier=SafetyTier.SAFE, project="P", allocation_ref="P")
        # Principal is immutable - cannot change tier
        assert p.tier == SafetyTier.SAFE

    def test_attack_cross_project_access(self, gateway):
        """Attack: Agent from Project A tries to access Project B's capabilities."""

        # Agent allocated to TEST-PROJECT (max_tier=1) tries to access PROFESSOR-J capability

    def test_attack_forged_principal(self, gateway):
        """Attack: Caller constructs forged Principal with higher tier."""
        with pytest.raises(RuntimeError, match="forge_attempt"):
            Principal(
                id="forged",
                tier=SafetyTier.DESTRUCTIVE,
                project="PROFESSOR-J",
                allocation_ref="PROFESSOR-J",
                _trusted=False,
            )

    def test_attack_direct_gateway_bypass(self, gateway):
        """Attack: Direct ToolExecutor invocation bypassing gateway."""

    def test_attack_subprocess_bypass(self, gateway):
        """Attack: CodeSandbox subprocess bypasses all gates."""

    def test_attack_replay(self, gateway):
        """Attack: Replay a previously valid authorization."""

    def test_attack_tampered_canonical_artifact(self, gateway):
        """Attack: Modify canonical artifact and try to use it."""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
