"""Tool execution subsystem — safety-gated, tiered tool dispatch.

The :class:`ToolExecutor` is the single place a cognitive agent invokes a
capability. Every tool registers a :class:`SafetyTier`; the executor funnels
every call through the safety policy (injection + PII checks, and HITL approval
for DESTRUCTIVE tiers) before dispatching to the underlying callable. Phase 5
wires the code sandbox in here.
"""

from app.tools.executor import (
    RegisteredTool,
    ToolExecutor,
    ToolNotFoundError,
)

__all__ = ["ToolExecutor", "RegisteredTool", "ToolNotFoundError"]
