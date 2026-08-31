"""AuthorityGateway — the single authoritative execution boundary for all privileged operations.

All privileged execution in the system must pass through this gateway. The gateway
enforces:
- Principal authentication (context must have a valid Principal)
- Project verification
- Allocation enforcement (agent allowed for project, tier ceiling)
- Capability authorization (capability granted to project, tier ceiling)
- Safety policy enforcement (injection/PII/HITL)
- Provenance recording on decisions
- Audit logging

No privileged operation should bypass this gateway. ToolExecutor, MCPServerManager,
CodeSandbox, and CLI entry points must route through AuthorityGateway.execute().
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.tools.executor import ToolExecutor

import yaml

from app.authority.principal import Principal, require_principal
from app.domain.tool import SafetyTier
from app.exceptions import ProfessorError
from app.guardrails.policy import HITLRequiredError, SafetyGateError, SafetyPolicy
from app.tools.executor import ToolExecutor, ToolNotFoundError

logger = logging.getLogger(__name__)


class AuthorizationError(ProfessorError):
    """Raised when an authorization check fails."""

    code = "AUTHORIZATION_FAILED"


class AllocationError(ProfessorError):
    """Raised when allocation check fails."""

    code = "ALLOCATION_VIOLATION"


class TierExceededError(ProfessorError):
    """Raised when capability tier exceeds principal's maximum."""

    code = "TIER_EXCEEDED"


class CapabilityNotGrantedError(ProfessorError):
    """Raised when capability is not granted to the project."""

    code = "CAPABILITY_NOT_GRANTED"


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    """Record of an authorization decision for audit."""

    timestamp: str
    principal_id: str
    project: str
    capability: str
    capability_tier: str
    principal_tier: str
    max_tier: int | None
    allowed: bool
    reason: str
    provenance_source: str


@dataclass(frozen=True, slots=True)
class GatewayResult:
    """Result of a gateway execution."""

    success: bool
    result: Any
    decision: AuthorizationDecision
    provenance: dict[str, Any]


class AuthorityGateway:
    """The single authoritative execution boundary for all privileged operations."""

    def __init__(
        self,
        tool_executor: ToolExecutor,
        safety_policy: SafetyPolicy,
        allocation_path: str | Path = "authority/allocation.yaml",
        permission_manifest_path: str | Path = "authority/permission-manifest.yaml",
        audit_log_path: str | Path | None = None,
    ) -> None:
        self.tool_executor = tool_executor
        self.safety_policy = safety_policy
        self.allocation_path = Path(allocation_path)
        self.permission_manifest_path = Path(permission_manifest_path)
        self.audit_log_path = Path(audit_log_path) if audit_log_path else None
        self._allocation_cache: dict | None = None
        self._permission_cache: dict | None = None
        self._audit_entries: list[AuthorizationDecision] = []

    def _load_allocation(self) -> dict:
        """Load and cache allocation.yaml."""
        if self._allocation_cache is None:
            if not self.allocation_path.is_file():
                raise RuntimeError(f"Allocation file not found: {self.allocation_path}")
            self._allocation_cache = yaml.safe_load(self.allocation_path.read_text()) or {}
        return self._allocation_cache

    def _load_permission_manifest(self) -> dict:
        """Load and cache permission-manifest.yaml."""
        if self._permission_cache is None:
            if not self.permission_manifest_path.is_file():
                raise RuntimeError(
                    f"Permission manifest not found: {self.permission_manifest_path}"
                )
            self._permission_cache = yaml.safe_load(self.permission_manifest_path.read_text()) or {}
        return self._permission_cache

    def invalidate_caches(self) -> None:
        """Invalidate cached manifests (call after external modification)."""
        self._allocation_cache = None
        self._permission_cache = None

    def _get_project_allocation(self, project: str) -> dict[str, Any] | None:
        """Get allocation configuration for a project."""
        allocation = self._load_allocation()
        repo_alloc = allocation.get("repo_allocation")
        if not repo_alloc:
            return None
        return repo_alloc.get(project)

    def _get_granted_capabilities(self, project: str) -> list[str]:
        """Get list of capability IDs granted to a project.

        Supports two manifest structures:
        1. repo_grants list with entries having 'repo' and 'capabilities' fields
        2. repo_allocation dict with project names as keys, each having 'capabilities' list
        """
        manifest = self._load_permission_manifest()

        # Try repo_grants format first
        for entry in manifest.get("repo_grants", []):
            if entry.get("repo") == project:
                caps = entry.get("capabilities")
                if caps:
                    return caps

        # Try repo_allocation format (used in current manifest)
        repo_alloc = manifest.get("repo_allocation", {})
        project_config = repo_alloc.get(project, {})
        caps = project_config.get("capabilities")
        if caps:
            return caps

        return []

    def _get_capability_tier(self, capability: str) -> SafetyTier | None:
        """Get the declared tier for a capability from the registry."""
        # Check tool executor first
        if self.tool_executor.has_tool(capability):
            tool = self.tool_executor._tools.get(capability)
            if tool:
                return tool.tier
        # Check MCP tools (would need MCP registry integration)
        return None

    def _check_allocation(self, principal: Principal, capability: str) -> None:
        """Verify principal is allocated to the project and capability is granted."""
        allocation = self._get_project_allocation(principal.project)
        if not allocation:
            raise AllocationError(f"Project '{principal.project}' not found in allocation manifest")

        # Check agent is allocated to this project
        allowed_agents = allocation.get("agents", [])
        if principal.id not in allowed_agents:
            raise AllocationError(
                f"Agent '{principal.id}' not allocated to project '{principal.project}'. "
                f"Allowed: {allowed_agents}"
            )

        # Check tier ceiling
        max_tier = allocation.get("max_tier")
        if max_tier is not None:
            tier_order = {SafetyTier.SAFE: 0, SafetyTier.SENSITIVE: 1, SafetyTier.DESTRUCTIVE: 2}
            principal_tier_num = tier_order.get(principal.tier, 0)
            if principal_tier_num > max_tier:
                raise TierExceededError(
                    f"Principal tier {principal.tier.value} exceeds project max tier {max_tier}"
                )

        # Check capability is granted to project
        granted = self._get_granted_capabilities(principal.project)
        if capability not in granted:
            raise CapabilityNotGrantedError(
                f"Capability '{capability}' not granted to project '{principal.project}'. "
                f"Granted: {granted}"
            )

    def _check_tier(self, principal: Principal, capability: str) -> None:
        """Verify principal's tier permits the capability's tier."""
        capability_tier = self._get_capability_tier(capability)
        if capability_tier is None:
            # Unknown capability - deny by default
            raise CapabilityNotGrantedError(f"Capability '{capability}' not registered")
        if not principal.can_execute_tier(capability_tier):
            raise TierExceededError(
                "Principal tier "
                f"{principal.tier.value} cannot execute "
                f"{capability_tier.value} capability"
            )

    def _record_decision(self, decision: AuthorizationDecision) -> None:
        """Record authorization decision for audit."""
        self._audit_entries.append(decision)
        if self.audit_log_path:
            self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.audit_log_path.open("a") as f:
                f.write(json.dumps(decision.__dict__) + "\n")

    def _build_provenance(
        self, source: str, capability: str, args: dict[str, Any]
    ) -> dict[str, Any]:
        """Build provenance record for the operation."""
        return {
            "source": source,
            "capability": capability,
            "timestamp": datetime.now(UTC).isoformat(),
            "args_summary": {k: type(v).__name__ for k, v in args.items()},
        }

    @contextmanager
    def _principal_context(self, principal: Principal):
        """Context manager to set principal for the duration of execution."""
        from app.authority.principal import reset_current_principal, set_current_principal

        token = set_current_principal(principal)
        try:
            yield
        finally:
            reset_current_principal(token)

    async def execute(
        self,
        capability: str,
        args: dict[str, Any],
        provenance_source: str = "agent",
    ) -> GatewayResult:
        """Execute a capability through the authoritative gateway.

        This is the single entry point for ALL privileged execution.
        """
        principal = require_principal()

        # Determine capability tier
        capability_tier = self._get_capability_tier(capability)
        if capability_tier is None:
            # Try to find in tool executor
            if self.tool_executor.has_tool(capability):
                tool = self.tool_executor._tools[capability]
                capability_tier = tool.tier
            else:
                raise CapabilityNotGrantedError(f"Capability '{capability}' not registered")

        # Authorization checks
        self._check_allocation(principal, capability)
        self._check_tier(principal, capability)

        # Safety policy check (injection, PII, HITL)
        try:
            self.safety_policy.check(
                tool=capability,
                args=args,
                tier=capability_tier,
                description=f"Gateway execution of {capability}",
            )
        except (SafetyGateError, HITLRequiredError) as e:
            allocation_for_max = self._get_project_allocation(principal.project)
            max_tier_val = allocation_for_max.get("max_tier") if allocation_for_max else None
            decision = AuthorizationDecision(
                timestamp=datetime.now(UTC).isoformat(),
                principal_id=principal.id,
                project=principal.project,
                capability=capability,
                capability_tier=capability_tier.value,
                principal_tier=principal.tier.value,
                max_tier=max_tier_val,
                allowed=False,
                reason=str(e),
                provenance_source=provenance_source,
            )
            self._record_decision(decision)
            raise

        # Record positive decision
        allocation = self._get_project_allocation(principal.project)
        decision = AuthorizationDecision(
            timestamp=datetime.now(UTC).isoformat(),
            principal_id=principal.id,
            project=principal.project,
            capability=capability,
            capability_tier=capability_tier.value,
            principal_tier=principal.tier.value,
            max_tier=allocation.get("max_tier") if allocation else None,
            allowed=True,
            reason="authorized",
            provenance_source=provenance_source,
        )
        self._record_decision(decision)

        # Execute with principal context
        provenance = self._build_provenance(provenance_source, capability, args)

        with self._principal_context(
            Principal.create(
                id=principal.id,
                tier=principal.tier,
                project=principal.project,
                allocation_ref=principal.allocation_ref,
            )
        ):
            try:
                result = await self.tool_executor.execute(capability, args)
                success = result.get("success", False)
            except ToolNotFoundError:
                success = False
                raise
            except Exception as e:
                logger.error(f"Gateway execution failed for {capability}: {e}")
                success = False
                raise

        return GatewayResult(
            success=success,
            result=result,
            decision=decision,
            provenance=provenance,
        )

    def get_audit_entries(self) -> list[AuthorizationDecision]:
        """Get all recorded audit entries."""
        return list(self._audit_entries)

    def clear_audit(self) -> None:
        """Clear in-memory audit entries (file log persists)."""
        self._audit_entries.clear()


# Singleton instance (set at bootstrap)
_gateway: AuthorityGateway | None = None


def get_gateway() -> AuthorityGateway | None:
    """Get the current gateway instance."""
    return _gateway


def set_gateway(gateway: AuthorityGateway) -> None:
    """Set the global gateway instance (called at bootstrap)."""
    global _gateway
    _gateway = gateway


def require_gateway() -> AuthorityGateway:
    """Get the gateway or raise if not initialized."""
    if _gateway is None:
        raise RuntimeError("AuthorityGateway not initialized. Call set_gateway() at bootstrap.")
    return _gateway
