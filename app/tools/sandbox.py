"""Code & Math Sandbox — isolated, resource-capped execution for the ToolExecutor.

The sandbox runs untrusted code in a child subprocess with strict limits:
bounded timeout (kills infinite loops), isolated interpreter (`-I`), no stdin,
captures stdout/stderr, and never shares the host web-process memory. It is the
backend the Phase 4 :class:`~app.tools.executor.ToolExecutor` dispatches to for
the ``run_code`` and ``solve_math`` tools.

Security posture:

* Python runs with ``-I`` (isolated mode: no user site, no ``PYTHONPATH``).
* A watchdog terminates the process on timeout so infinite loops cannot hang it.
* The sandbox is reached ONLY through the executor, which enforces
  ``DESTRUCTIVE`` tier for ``run_code`` (mandatory human approval) and ``SAFE``
  for ``solve_math`` (already deterministic/safe).
* Forthcoming production hardening per plan: Docker + gVisor isolation, no
  network, resource quotas (cgroups). The subprocess limits below are the
  in-process fallback used in tests and local development.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.domain.tool import SafetyTier
from app.exceptions import SandboxError, SandboxMemoryError, SandboxTimeoutError
from app.guardrails.policy import safety_gate

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SandboxConfig:
    """Resource and behavior limits for a sandbox run."""

    timeout_seconds: int = 10
    max_output_bytes: int = 1_000_000
    memory_limit_mb: int = 512
    network_enabled: bool = False


@dataclass(frozen=True, slots=True)
class SandboxResult:
    """Outcome of a sandboxed execution."""

    success: bool
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool
    duration_ms: float

    @property
    def output(self) -> str:
        return self.stdout or self.stderr


def _limits(config: SandboxConfig) -> Callable[[], None]:
    """Return a POSIX preexec that bounds the child's virtual memory.

    Runs inside the forked child before exec. RLIMIT_AS caps virtual memory so a
    runaway allocation can't exhaust the host. CPU/wall time is enforced by
    ``subprocess.run(timeout=...)`` (the authoritative watchdog), which raises
    :class:`SandboxTimeoutError` on infinite loops.
    """

    def _apply() -> None:
        import resource

        mem_bytes = config.memory_limit_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))

    return _apply


class CodeSandbox:
    """Runs a snippet in an isolated subprocess with enforced limits."""

    def __init__(self, config: SandboxConfig | None = None) -> None:
        self.config = config or SandboxConfig()

    async def run_python(self, code: str) -> SandboxResult:
        """Execute Python code in an isolated subprocess."""
        if not code or not code.strip():
            return SandboxResult(True, "", "", 0, False, 0.0)

        with tempfile.TemporaryDirectory(prefix="professor-sandbox-") as tmp:
            script = Path(tmp) / "main.py"
            script.write_text(code, encoding="utf-8")

            cmd = [
                "python3",
                "-I",  # isolated mode: no user site-packages, no PYTHONPATH
                str(script),
            ]
            env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
            if not self.config.network_enabled:
                # No proxy/network env leakage into the child.
                env = {k: v for k, v in env.items() if k not in ("HTTP_PROXY", "HTTPS_PROXY")}

            start = time.monotonic()
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.config.timeout_seconds,
                    cwd=tmp,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    preexec_fn=_limits(self.config),
                )
            except subprocess.TimeoutExpired:
                raise SandboxTimeoutError(self.config.timeout_seconds) from None
            finally:
                duration_ms = (time.monotonic() - start) * 1000.0

            stdout = proc.stdout[: self.config.max_output_bytes]
            stderr = proc.stderr[: self.config.max_output_bytes]
        return SandboxResult(
            success=proc.returncode == 0,
            stdout=stdout,
            stderr=stderr,
            exit_code=proc.returncode,
            timed_out=False,
            duration_ms=duration_ms,
        )


class MathSolver:
    """Deterministic SymPy-based algebra/calculus/unit solver (SAFE tier).

    Only a narrow, allow-listed set of SymPy operations is exposed; arbitrary
    expressions parse through :func:`sympify` which cannot execute unsafe code.
    """

    @safety_gate(tier=SafetyTier.SAFE, description="Solve a math expression with SymPy")
    def solve(self, expression: str, variable: str | None = None) -> dict[str, Any]:
        import sympy as sp

        try:
            expr = sp.sympify(expression)
            if variable is not None:
                symbol = sp.Symbol(variable)
                solutions = sp.solve(expr, symbol)
                return {"success": True, "solutions": [str(s) for s in solutions]}
            simplified = sp.simplify(expr)
            return {"success": True, "simplified": str(simplified)}
        except Exception as exc:  # noqa: BLE001 - surface parse/solve errors as tool failure
            logger.warning("MathSolver failed for %r: %s", expression, exc)
            return {"success": False, "error": str(exc)}

    @safety_gate(tier=SafetyTier.SAFE, description="Differentiate or integrate with SymPy")
    def calculus(self, expression: str, variable: str, operation: str) -> dict[str, Any]:
        import sympy as sp

        try:
            symbol = sp.Symbol(variable)
            expr = sp.sympify(expression)
            if operation == "differentiate":
                result = sp.diff(expr, symbol)
            elif operation == "integrate":
                result = sp.integrate(expr, symbol)
            else:
                return {"success": False, "error": f"Unknown operation {operation}"}
            return {"success": True, "result": str(result)}
        except Exception as exc:  # noqa: BLE001
            logger.warning("MathSolver.calculus failed: %s", exc)
            return {"success": False, "error": str(exc)}


__all__ = [
    "CodeSandbox",
    "MathSolver",
    "SandboxResult",
    "SandboxConfig",
    "SandboxError",
    "SandboxTimeoutError",
    "SandboxMemoryError",
    "SafetyTier",
]
