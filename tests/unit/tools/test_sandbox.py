"""Tests for the Phase 5 code/math sandbox and its ToolExecutor wiring."""

from __future__ import annotations

import pytest

from app.domain.tool import SafetyTier
from app.exceptions import HITLRequiredError, SandboxTimeoutError
from app.guardrails.policy import SafetyPolicy
from app.tools import CodeSandbox, MathSolver, SandboxConfig, ToolExecutor


@pytest.mark.asyncio
async def test_runs_python_and_captures_stdout() -> None:
    sb = CodeSandbox(SandboxConfig(timeout_seconds=5))
    result = await sb.run_python("print('hi'); print(6 * 7)")
    assert result.success is True
    assert "hi" in result.stdout
    assert "42" in result.stdout


@pytest.mark.asyncio
async def test_empty_code_is_clean_noop() -> None:
    sb = CodeSandbox()
    result = await sb.run_python("   \n  ")
    assert result.success is True
    assert result.stdout == ""


@pytest.mark.asyncio
async def test_infinite_loop_times_out() -> None:
    sb = CodeSandbox(SandboxConfig(timeout_seconds=2))
    with pytest.raises(SandboxTimeoutError):
        await sb.run_python("while True: pass")


@pytest.mark.asyncio
async def test_error_reported_not_raised() -> None:
    sb = CodeSandbox(SandboxConfig(timeout_seconds=5))
    result = await sb.run_python("raise ValueError('boom')")
    assert result.success is False
    assert "boom" in result.stderr


class TestMathSolver:
    def test_solve_quadratic(self) -> None:
        out = MathSolver().solve("x**2 - 9", "x")
        assert out["success"] is True
        assert set(out["solutions"]) == {"-3", "3"}

    def test_simplify(self) -> None:
        out = MathSolver().solve("x + x + x")
        assert out["success"] is True
        assert "3*x" in out["simplified"]

    def test_calculus_differentiate(self) -> None:
        out = MathSolver().calculus("x**3", "x", "differentiate")
        assert out["success"] is True
        assert "3*x**2" in out["result"]

    def test_calculus_unknown_op(self) -> None:
        out = MathSolver().calculus("x", "x", "bogus")
        assert out["success"] is False


class TestExecutorWiring:
    def _executor(self, approve: bool = True) -> ToolExecutor:
        policy = SafetyPolicy(approval_callback=lambda tool, args, desc: approve)
        ex = ToolExecutor(policy)
        ex.register_sandbox_tools()
        return ex

    @pytest.mark.asyncio
    async def test_run_code_is_destructive_needs_approval(self) -> None:
        ex = self._executor(approve=True)
        out = await ex.execute("run_code", {"code": "print(1 + 1)"})
        assert out["success"] is True
        assert "2" in out["stdout"]

    @pytest.mark.asyncio
    async def test_run_code_denied_raises_hitl(self) -> None:
        ex = self._executor(approve=False)
        with pytest.raises(HITLRequiredError):
            await ex.execute("run_code", {"code": "print(1)"})

    @pytest.mark.asyncio
    async def test_solve_math_safe_without_approval(self) -> None:
        ex = ToolExecutor(SafetyPolicy(approval_callback=None))
        ex.register_sandbox_tools()
        out = await ex.execute("solve_math", {"expression": "x**2 - 4", "variable": "x"})
        assert out["success"] is True

    def test_sandbox_tool_tiers(self) -> None:
        ex = self._executor()
        desc = {t["name"]: t for t in ex.list_tools()}
        assert desc["run_code"]["tier"] == SafetyTier.DESTRUCTIVE.value
        assert desc["solve_math"]["tier"] == SafetyTier.SAFE.value
