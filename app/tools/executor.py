"""ToolExecutor — safety-gated dispatch for cognitive agents.

Tools are callables registered with a declared :class:`SafetyTier`. Executing a
tool always passes through the :class:`SafetyPolicy` (prompt-injection + PII
checks; HITL approval for DESTRUCTIVE), so no agent can reach a capability
without the gate. The underlying callable may be a plain function or a bound
skill's ``execute``.

This is the abstract seam Phase 5 fills with the code/math sandbox and Phase 4
fills with MCP tool invocation.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.domain.gamedev import EngineTarget
from app.domain.tool import SafetyTier
from app.exceptions import CapabilityRegistrationError, ProfessorError
from app.guardrails.policy import SafetyPolicy
from app.tools.sandbox import CodeSandbox, MathSolver

if TYPE_CHECKING:
    from app.gamedev import GameDevAgent
    from app.workspace import WorkspaceManager

logger = logging.getLogger(__name__)


class ToolNotFoundError(ProfessorError):
    """Raised when an unknown tool is invoked."""

    code = "TOOL_NOT_FOUND"

    def __init__(self, name: str) -> None:
        super().__init__(f"No such tool: {name}")
        self.name = name


@dataclass(frozen=True, slots=True)
class RegisteredTool:
    """A tool available to the executor."""

    name: str
    tier: SafetyTier
    description: str
    fn: Callable[..., Any]  # called with parsed args


class ToolExecutor:
    """Dispatch table + safety gate for tool execution."""

    def __init__(
        self,
        policy: SafetyPolicy | None = None,
        *,
        register_policy: Callable[..., bool] | None = None,
        blessed_registrar: bool = False,
        ledger: Any | None = None,
    ) -> None:
        self.policy = policy or SafetyPolicy(approval_callback=None)
        self._tools: dict[str, RegisteredTool] = {}
        self._register_policy: Callable[..., bool] | None = register_policy
        self._blessed_registrar = blessed_registrar
        # Optional immutable audit ledger (Phase 2 / P9). Best-effort: a ledger failure must
        # never fail the operation it is recording.
        self._ledger = ledger

    def _ledger_event(
        self, action: str, resource: str, approved: bool | None, reason: str = ""
    ) -> None:
        if self._ledger is None:
            return
        try:
            self._ledger.append(
                action=action,
                principal="professor:tool-executor",
                resource=resource,
                approved=approved,
                detail={"reason": reason} if reason else None,
            )
        except Exception:  # noqa: BLE001 - audit is best-effort
            logger.warning("ledger append failed for %s %s", action, resource)

    def _check_register(self, name: str, tier: SafetyTier, description: str) -> None:
        """Consult the registration policy (if any) and deny with a typed error on refusal."""
        if self._register_policy is None:
            self._ledger_event("register", name, True)
            return
        allowed = self._register_policy(name, tier, self._blessed_registrar)
        if not allowed:
            self._ledger_event("register-denied", name, False, f"tier {tier.value}")
            raise CapabilityRegistrationError(
                capability=name,
                reason=(
                    f"tier {tier.value} is not permitted for a non-blessed registrar "
                    "(DESTRUCTIVE self-registration denied)"
                ),
            )
        self._ledger_event("register", name, True)

    def register(self, tool: RegisteredTool) -> None:
        """Register a tool for dispatch (gated by the optional registration policy)."""
        self._check_register(tool.name, tool.tier, tool.description)
        self._tools[tool.name] = tool

    def register_fn(
        self,
        name: str,
        fn: Callable[..., Any],
        *,
        tier: SafetyTier,
        description: str,
    ) -> None:
        self.register(RegisteredTool(name=name, tier=tier, description=description, fn=fn))

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def list_tools(self) -> list[dict[str, Any]]:
        """Describe registered tools (for agent tool-calling schemas)."""
        return [
            {
                "name": t.name,
                "tier": t.tier.value,
                "description": t.description,
            }
            for t in self._tools.values()
        ]

    def register_mcp_tools(self, manager: Any) -> None:
        """Expose MCP-discovered tools through this executor.

        Each MCP tool is registered as a wrapper that calls the MCP server
        manager. Routing through :meth:`execute` means every MCP call also
        passes the executor's safety gate (defense in depth — the MCP manager
        additionally fails closed if it has no policy of its own).
        """
        for tool in manager.list_tools():
            self._register_mcp_tool(tool, manager)

    def _register_mcp_tool(self, tool: Any, manager: Any) -> None:
        from app.domain.tool import SafetyTier as _Tier

        tier = getattr(tool, "tier", None) or _Tier.SENSITIVE
        description = getattr(tool, "description", "") or (
            f"MCP tool '{getattr(tool, 'name', '?')}'"
        )
        name = getattr(tool, "name", None)
        if not name or self.has_tool(name):
            return

        async def _call(**kwargs: Any) -> dict[str, Any]:
            try:
                result = await manager.call_tool(name, kwargs)
            except Exception as exc:  # noqa: BLE001 - surface as tool failure
                return {"success": False, "error": str(exc), "tool": name}
            if isinstance(result, dict):
                result.setdefault("success", True)
                return result
            return {"success": True, "result": result, "tool": name}

        self.register_fn(name, _call, tier=tier, description=description)
        logger.info("Registered MCP tool into executor: %s (tier=%s)", name, tier.value)

    def register_sandbox_tools(
        self,
        sandbox: CodeSandbox | None = None,
        solver: MathSolver | None = None,
    ) -> None:
        """Wire the Phase 5 sandbox + math solver into the executor.

        ``run_code`` is DESTRUCTIVE (executes untrusted code -> HITL required);
        ``solve_math`` is SAFE (deterministic SymPy).
        """
        sbx = sandbox or CodeSandbox()
        mth = solver or MathSolver()

        async def _run_code(code: str) -> dict[str, Any]:
            result = await sbx.run_python(code)
            if result.timed_out:
                return {"success": False, "error": "Sandbox execution timed out"}
            return {
                "success": result.success,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.exit_code,
                "duration_ms": result.duration_ms,
            }

        self.register_fn(
            "run_code",
            _run_code,
            tier=SafetyTier.DESTRUCTIVE,
            description="Run untrusted Python code in the sandbox",
        )
        self.register_fn(
            "solve_math",
            mth.solve,
            tier=SafetyTier.SAFE,
            description="Solve or simplify a math expression",
        )
        self.register_fn(
            "math_calculus",
            mth.calculus,
            tier=SafetyTier.SAFE,
            description="Differentiate or integrate an expression",
        )

    def register_gamedev_tools(
        self,
        gamedev: GameDevAgent,
        workspace: WorkspaceManager,
        sandbox: CodeSandbox | None = None,
    ) -> None:
        """Wire Game Development capability tools into the executor."""

        def _gamedev_plan(prompt: str, target: str = "pure_core") -> dict[str, Any]:
            target_enum = (
                EngineTarget(target)
                if target in [e.value for e in EngineTarget]
                else EngineTarget.PURE_CORE
            )
            spec = gamedev.plan_project(prompt, target=target_enum)
            return {
                "title": spec.title,
                "genre": spec.genre.value,
                "target_engine": spec.target_engine.value,
                "components": [c.name for c in spec.components],
                "max_players": spec.max_players,
            }

        def _gamedev_scaffold(prompt: str, project_dir: str | None = None) -> dict[str, Any]:
            spec = gamedev.plan_project(prompt)
            return gamedev.scaffold(spec, workspace, project_dir=project_dir)

        def _gamedev_validate(project_dir: str = "") -> dict[str, Any]:
            report = gamedev.validate(workspace, project_dir)
            return {
                "is_valid": report.is_valid,
                "summary": report.summary,
                "errors": [v.message for v in report.violations],
                "warnings": [w.message for w in report.warnings],
            }

        async def _gamedev_verify(
            project_dir: str = "", target: str = "pure_core"
        ) -> dict[str, Any]:
            box = sandbox or CodeSandbox()
            target_enum = (
                EngineTarget(target)
                if target in [e.value for e in EngineTarget]
                else EngineTarget.PURE_CORE
            )
            report = await gamedev.verify_game(workspace, project_dir, box, target=target_enum)
            return {
                "success": report.success,
                "passed_count": report.passed_count,
                "failed_count": report.failed_count,
                "exit_code": report.exit_code,
                "duration_ms": report.duration_ms,
                "stdout": report.stdout,
                "stderr": report.stderr,
                "error": report.error,
                "timed_out": report.timed_out,
            }

        self.register_fn(
            "gamedev_plan",
            _gamedev_plan,
            tier=SafetyTier.SAFE,
            description="Plan game architecture and component requirements",
        )
        self.register_fn(
            "gamedev_scaffold",
            _gamedev_scaffold,
            tier=SafetyTier.SAFE,
            description="Scaffold game project structure and pure rule contracts in workspace",
        )
        self.register_fn(
            "gamedev_validate",
            _gamedev_validate,
            tier=SafetyTier.SAFE,
            description="Validate game architecture compliance and domain purity",
        )
        self.register_fn(
            "gamedev_verify",
            _gamedev_verify,
            tier=SafetyTier.DESTRUCTIVE,
            description="Execute headless game tests in isolated sandbox",
        )

    async def execute(self, name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        """Run a tool through the safety gate and return its result.

        Raises :class:`~app.exceptions.HITLRequiredError`/``SafetyGateError`` for
        denied calls; execution failures are returned as ``{"success": False}``.
        """
        tool = self._tools.get(name)
        if tool is None:
            raise ToolNotFoundError(name)

        args = args or {}
        sanitized = self.policy.check(tool.name, args, tool.tier, tool.description)
        logger.info("tool execute: %s tier=%s args=%s", tool.name, tool.tier.value, sanitized)

        try:
            result = tool.fn(**args)
            if inspect.iscoroutine(result):
                result = await result
        except Exception as exc:  # noqa: BLE001 - surface as tool failure
            logger.exception("tool %s failed: %s", tool.name, exc)
            return {"success": False, "error": str(exc), "tool": tool.name}
        if isinstance(result, dict):
            merged = {**result, "tool": tool.name}
            merged.setdefault("success", True)
            return merged
        return {"success": True, "result": result, "tool": tool.name}


__all__ = [
    "ToolExecutor",
    "RegisteredTool",
    "ToolNotFoundError",
]
