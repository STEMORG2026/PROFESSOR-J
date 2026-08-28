"""Tool execution subsystem — safety-gated, tiered tool dispatch.

The :class:`ToolExecutor` is the single place a cognitive agent invokes a
capability. Every tool registers a :class:`SafetyTier`; the executor funnels
every call through the safety policy (injection + PII checks, and HITL approval
for DESTRUCTIVE tiers) before dispatching to the underlying callable.

Phase 5 adds the code/math sandbox (``CodeSandbox``, ``MathSolver``), wired as
``run_code`` (DESTRUCTIVE) and ``solve_math`` (SAFE) via
:meth:`~app.tools.executor.ToolExecutor.register_sandbox_tools`.
"""

from app.tools.executor import (
    RegisteredTool,
    ToolExecutor,
    ToolNotFoundError,
)
from app.tools.sandbox import (
    CodeSandbox,
    MathSolver,
    SandboxConfig,
    SandboxResult,
)

__all__ = [
    "ToolExecutor",
    "RegisteredTool",
    "ToolNotFoundError",
    "CodeSandbox",
    "MathSolver",
    "SandboxConfig",
    "SandboxResult",
]
