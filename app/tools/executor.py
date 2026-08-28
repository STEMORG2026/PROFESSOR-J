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

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.domain.tool import SafetyTier
from app.exceptions import ProfessorError
from app.guardrails.policy import SafetyPolicy

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

    def __init__(self, policy: SafetyPolicy | None = None) -> None:
        self.policy = policy or SafetyPolicy(approval_callback=None)
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, tool: RegisteredTool) -> None:
        """Register a tool for dispatch."""
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
