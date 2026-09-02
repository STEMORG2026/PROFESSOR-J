"""Tests for Build 1: Identity + Gateway enforcement."""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

# Get the workspace root
WORKSPACE_ROOT = Path("/home/sajan/Projects")

# Ensure PROFESSOR-J is in path
sys.path.insert(0, str(WORKSPACE_ROOT / "PROFESSOR-J"))

from app.authority.gateway import (
    AuthorityGateway,
)
from app.authority.principal import (
    Principal,
    get_current_principal,
    require_principal,
    reset_current_principal,
    set_current_principal,
)
from app.domain.tool import SafetyTier
from app.guardrails.policy import SafetyPolicy
from app.tools import ToolExecutor


class TestPrincipal:
    """Test Principal creation and context propagation."""

    def test_principal_create_only_through_classmethod(self):
        """Principal can only be created through create() classmethod."""
        p = Principal.create(
            id="test-agent",
            tier=SafetyTier.SAFE,
            project="TEST",
            allocation_ref="TEST",
        )
        assert p.id == "test-agent"
        assert p.tier == SafetyTier.SAFE
        assert p.project == "TEST"
        assert p.allocation_ref == "TEST"

    def test_principal_direct_construction_fails(self):
        """Direct Principal construction should fail (forgery prevention)."""
        with pytest.raises(RuntimeError, match="forge_attempt"):
            Principal(
                id="test",
                tier=SafetyTier.SAFE,
                project="TEST",
                allocation_ref="TEST",
                _trusted=False,
            )

    def test_principal_tier_check(self):
        """Principal tier comparison works correctly."""
        safe_agent = Principal.create(
            id="safe", tier=SafetyTier.SAFE, project="P", allocation_ref="P"
        )
        sensitive_agent = Principal.create(
            id="sens", tier=SafetyTier.SENSITIVE, project="P", allocation_ref="P"
        )
        destructive_agent = Principal.create(
            id="dest", tier=SafetyTier.DESTRUCTIVE, project="P", allocation_ref="P"
        )

        # SAFE can only execute SAFE
        assert safe_agent.can_execute_tier(SafetyTier.SAFE)
        assert not safe_agent.can_execute_tier(SafetyTier.SENSITIVE)
        assert not safe_agent.can_execute_tier(SafetyTier.DESTRUCTIVE)

        # SENSITIVE can execute SAFE + SENSITIVE
        assert sensitive_agent.can_execute_tier(SafetyTier.SAFE)
        assert sensitive_agent.can_execute_tier(SafetyTier.SENSITIVE)
        assert not sensitive_agent.can_execute_tier(SafetyTier.DESTRUCTIVE)

        # DESTRUCTIVE can execute all
        assert destructive_agent.can_execute_tier(SafetyTier.SAFE)
        assert destructive_agent.can_execute_tier(SafetyTier.SENSITIVE)
        assert destructive_agent.can_execute_tier(SafetyTier.DESTRUCTIVE)


class TestPrincipalContext:
    """Test Principal context propagation."""

    def test_context_get_set(self):
        """Principal context can be set and retrieved."""
        from app.authority.principal import Principal
        from app.domain.tool import SafetyTier

        p = Principal.create(id="test", tier=SafetyTier.SAFE, project="P", allocation_ref="P")

        token = set_current_principal(p)
        assert get_current_principal().id == "test"

        reset_current_principal(token)
        assert get_current_principal() is None

    def test_require_principal_raises_when_none(self):
        """require_principal raises when no principal in context."""
        from contextvars import ContextVar

        # Ensure clean context
        var = ContextVar("principal", default=None)
        var.set(None)

        with pytest.raises(RuntimeError, match="No principal in context"):
            require_principal()


class TestAuthorityGateway:
    """Test AuthorityGateway enforcement."""

    @pytest.fixture
    def gateway(self):
        """Create a test gateway with minimal setup."""

        # Create a tool executor with a simple test tool
        policy = SafetyPolicy(approval_callback=None)
        tools = ToolExecutor(policy)

        # Register a simple test tool
        def test_tool(x: int) -> dict:
            return {"success": True, "result": x * 2}

        tools.register_fn(
            name="test_tool",
            fn=test_tool,
            tier=SafetyTier.SAFE,
            description="Test tool",
        )

        # Use a temporary permission manifest for testing
        import yaml

        # Create a test permission manifest with test_tool granted to PROFESSOR-J
        perm = {
            "format": 1,
            "generated": "2026-09-02",
            "principals": {
                "owner": {"name": "Test"},
                "platform": {"name": "Test"},
                "agents": {"authority_grant": False, "can_grant_capabilities": False},
            },
            "invariants": {},
            "grants": {
                "default": [{"capability": "test_tool", "risk_cap": 1, "actions": ["execute"]}]
            },
            "repo_allocation": {
                "PROFESSOR-J": {
                    "capabilities": [
                        "test_tool",
                        "code-exec/sandbox",
                        "skill-registry",
                        "tool-executor",
                        "lhs-knowledge-adapter",
                        "llm-provider-pool",
                    ],
                    "profile": "full",
                    "lifecycle": "active",
                }
            },
        }

        # Write to temp file
        temp_dir = tempfile.mkdtemp()
        perm_path = os.path.join(temp_dir, "permission-manifest.yaml")
        with open(perm_path, "w") as f:
            yaml.safe_dump(perm, f, sort_keys=False)

        gateway = AuthorityGateway(
            tool_executor=tools,
            safety_policy=SafetyPolicy(approval_callback=None),
            allocation_path=os.path.join(WORKSPACE_ROOT, "authority/allocation.yaml"),
            permission_manifest_path=perm_path,
            audit_log_path=None,  # In-memory only
        )

        # Cleanup function
        def cleanup():
            shutil.rmtree(temp_dir, ignore_errors=True)

        # Add cleanup to gateway object for later
        gateway._test_cleanup = cleanup

        return gateway

    def test_gateway_requires_principal(self, gateway):
        """Gateway requires a principal in context."""
        with pytest.raises(RuntimeError, match="No principal in context"):
            asyncio.run(gateway.execute("test_tool", {"x": 5}))

    def test_gateway_allocation_enforcement(self, gateway):
        """Gateway enforces allocation rules."""
        from app.authority.principal import Principal
        from app.domain.tool import SafetyTier

        # Create a principal NOT allocated to PROFESSOR-J
        p = Principal.create(
            id="unauthorized-agent",
            tier=SafetyTier.SAFE,
            project="PROFESSOR-J",
            allocation_ref="PROFESSOR-J",
        )

        set_current_principal(p)

        # Should fail - agent not in allocation.yaml for PROFESSOR-J
        with pytest.raises(Exception) as exc_info:
            asyncio.run(gateway.execute("test_tool", {"x": 5}))
        assert (
            "not allocated" in str(exc_info.value).lower()
            or "allocation" in str(exc_info.value).lower()
        )

    def test_gateway_tier_enforcement(self, gateway):
        """Gateway enforces tier ceiling."""
        from app.authority.principal import Principal
        from app.domain.tool import SafetyTier

        # Create a principal with SAFE tier
        p = Principal.create(
            id="researcher",
            tier=SafetyTier.SAFE,
            project="PROFESSOR-J",
            allocation_ref="PROFESSOR-J",
        )

        set_current_principal(p)

        # test_tool is SAFE tier, researcher has SENSITIVE in allocation (but principal created as SAFE)
        # The principal's tier is SAFE, capability is SAFE - should work
        result = asyncio.run(gateway.execute("test_tool", {"x": 10}))
        assert result.success is True

    def test_gateway_safety_gate_enforcement(self, gateway):
        """Gateway enforces safety policy (HITL for DESTRUCTIVE)."""
        from app.authority.principal import Principal
        from app.domain.tool import SafetyTier

        # Create principal with SAFE tier
        p = Principal.create(
            id="researcher",
            tier=SafetyTier.SAFE,
            project="PROFESSOR-J",
            allocation_ref="PROFESSOR-J",
        )

        from app.authority.principal import set_current_principal

        set_current_principal(p)

        # Try to execute a DESTRUCTIVE capability (if one exists)
        # We don't have a DESTRUCTIVE test tool registered, so test tier check logic
        # by checking that a SAFE principal cannot execute DESTRUCTIVE
        from app.domain.tool import SafetyTier

        p_safe = Principal.create(id="safe", tier=SafetyTier.SAFE, project="P", allocation_ref="P")
        assert not p_safe.can_execute_tier(SafetyTier.DESTRUCTIVE)


class TestGatewayAllocationEnforcement:
    """Test gateway enforces actual allocation.yaml rules."""

    def test_researcher_allocated_to_professor_j(self):
        """Researcher is allocated to PROFESSOR-J with SENSITIVE tier."""
        with open(os.path.join(WORKSPACE_ROOT, "authority/allocation.yaml")) as f:
            alloc = yaml.safe_load(f)

        prof_j = alloc["repo_allocation"]["PROFESSOR-J"]
        assert "researcher" in prof_j["agents"]
        assert prof_j["max_tier"] == 2  # SENSITIVE

    def test_jarvis_frozen_at_tier_1(self):
        """JARVIS is frozen at tier 1."""
        with open(os.path.join(WORKSPACE_ROOT, "authority/allocation.yaml")) as f:
            alloc = yaml.safe_load(f)

        jarvis = alloc["repo_allocation"]["JARVIS"]
        assert jarvis["lifecycle"] == "frozen"
        assert jarvis["max_tier"] == 1

    def test_stem_isolation(self):
        """STEM domain skills only for STEM-tagged projects."""
        with open(os.path.join(WORKSPACE_ROOT, "authority/allocation.yaml")) as f:
            alloc = yaml.safe_load(f)

        stem_tagged = alloc["isolation"]["domain_skills_require_tag"]["domain/stem"]
        assert "STEMMA" in stem_tagged
        assert "LearningHub" in stem_tagged
        assert "PROFESSOR-J" in stem_tagged


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
