"""Comprehensive unit tests for GameDev headless verification and sandbox safety."""

import tempfile
from collections.abc import Generator

import pytest

from app.domain.gamedev import EngineTarget, GameGenre, GameProjectSpec, GameTestReport
from app.exceptions import HITLRequiredError
from app.gamedev.adapters.pure_core import PureCoreAdapter
from app.gamedev.agent import GameDevAgent
from app.gamedev.components import GameComponentCatalog
from app.guardrails.policy import SafetyPolicy
from app.tools.executor import ToolExecutor
from app.tools.sandbox import CodeSandbox, SandboxConfig, SandboxResult
from app.workspace.workspace import WorkspaceManager, WorkspaceSecurityError


@pytest.fixture
def temp_workspace() -> Generator[WorkspaceManager, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield WorkspaceManager(tmpdir)


@pytest.fixture
def sandbox() -> CodeSandbox:
    return CodeSandbox(SandboxConfig(timeout_seconds=5))


@pytest.mark.asyncio
async def test_successful_python_headless_verification(
    temp_workspace: WorkspaceManager, sandbox: CodeSandbox
) -> None:
    """1. Successful Python headless test execution."""
    agent = GameDevAgent()
    spec = GameProjectSpec(
        title="PyLudo",
        genre=GameGenre.BOARD_GAME,
        target_engine=EngineTarget.PURE_CORE,
        target_language="python",
        components=(
            GameComponentCatalog.dice_rng(),
            GameComponentCatalog.turn_manager(player_count=2),
        ),
    )
    agent.scaffold(spec, temp_workspace, "pyludo")

    report = await agent.verify_game(temp_workspace, "pyludo", sandbox)
    assert report.success
    assert report.exit_code == 0
    assert report.passed_count >= 1
    assert report.failed_count == 0
    assert report.error is None
    assert not report.timed_out


@pytest.mark.asyncio
async def test_csharp_test_output_parsing() -> None:
    """2. Successful C# headless test execution parsing."""
    adapter = PureCoreAdapter()

    mock_dotnet_stdout = """
  Determining projects to restore...
  All projects are up-to-date for restore.
  GameCore -> /workspace/ludo/bin/Debug/net8.0/GameCore.dll
  GameCoreTests -> /workspace/ludo/bin/Debug/net8.0/GameCoreTests.dll
Test run for /workspace/ludo/bin/Debug/net8.0/GameCoreTests.dll (.NETCoreApp,Version=v8.0)
Microsoft (R) Test Execution Command Line Tool Version 17.8.0

Passed!  - Failed:     0, Passed:     4, Skipped:     0, Total:     4, Duration: 12 ms
"""
    result = SandboxResult(
        success=True,
        stdout=mock_dotnet_stdout,
        stderr="",
        exit_code=0,
        timed_out=False,
        duration_ms=45.0,
    )

    report = adapter.parse_test_output(result)
    assert report.success
    assert report.passed_count == 4
    assert report.failed_count == 0
    assert report.error is None


@pytest.mark.asyncio
async def test_test_failure_produces_structured_diagnostics(
    temp_workspace: WorkspaceManager, sandbox: CodeSandbox
) -> None:
    """3. Test failure produces structured failure diagnostics."""
    agent = GameDevAgent()
    spec = GameProjectSpec(
        title="FailingGame",
        genre=GameGenre.BOARD_GAME,
        target_engine=EngineTarget.PURE_CORE,
        target_language="python",
    )
    agent.scaffold(spec, temp_workspace, "failing_game")

    # Inject a failing test
    failing_test = """
def test_deliberate_failure():
    assert 1 == 2, "Illegal move state"
"""
    temp_workspace.write("failing_game/tests/test_failure.py", failing_test)

    report = await agent.verify_game(temp_workspace, "failing_game", sandbox)
    assert not report.success
    assert report.exit_code != 0
    assert report.failed_count >= 1
    assert report.error is not None
    assert "failed" in report.error.lower() or "illegal move state" in report.stdout.lower()


@pytest.mark.asyncio
async def test_sandbox_timeout_enforced(temp_workspace: WorkspaceManager) -> None:
    """4. Timeout is enforced."""
    agent = GameDevAgent()
    spec = GameProjectSpec(
        title="HangingGame",
        genre=GameGenre.BOARD_GAME,
        target_engine=EngineTarget.PURE_CORE,
        target_language="python",
    )
    agent.scaffold(spec, temp_workspace, "hanging_game")

    # Inject an infinite loop / sleep
    hanging_test = """
import time
def test_infinite_loop():
    time.sleep(10)
"""
    temp_workspace.write("hanging_game/tests/test_hang.py", hanging_test)

    # 1 second timeout
    short_sandbox = CodeSandbox(SandboxConfig(timeout_seconds=1))
    report = await agent.verify_game(temp_workspace, "hanging_game", short_sandbox)

    assert not report.success
    assert report.timed_out
    assert report.exit_code == 124
    assert report.error is not None
    assert "timed out" in report.error.lower()


def test_workspace_path_escape_rejected(temp_workspace: WorkspaceManager) -> None:
    """5. Workspace/path escape is rejected."""
    with pytest.raises(WorkspaceSecurityError):
        temp_workspace._resolve("../../../etc/passwd")

    with pytest.raises(WorkspaceSecurityError):
        temp_workspace._resolve("/etc/shadow")


@pytest.mark.asyncio
async def test_unsafe_command_execution_rejected(sandbox: CodeSandbox) -> None:
    """6. Unsafe command execution is rejected by sandbox."""
    res = await sandbox.run_command(["rm", "-rf", "/"], cwd="/tmp")  # nosec B108
    assert not res.success
    assert "Executable 'rm' is not permitted" in res.stderr

    res2 = await sandbox.run_command(["bash", "-c", "echo pwned"], cwd="/tmp")  # nosec B108
    assert not res2.success
    assert "Executable 'bash' is not permitted" in res2.stderr


@pytest.mark.asyncio
async def test_gamedev_agent_consumes_verification(
    temp_workspace: WorkspaceManager, sandbox: CodeSandbox
) -> None:
    """7. GameDevAgent can consume verification results."""
    agent = GameDevAgent()
    spec = agent.plan_project("Create a Python board game rules engine")
    spec = GameProjectSpec(
        title=spec.title,
        genre=spec.genre,
        target_engine=spec.target_engine,
        target_language="python",
        components=spec.components,
    )
    scaffold_res = agent.scaffold(spec, temp_workspace, "agent_game")
    assert scaffold_res["success"]

    report = await agent.verify_game(temp_workspace, "agent_game", sandbox)
    assert isinstance(report, GameTestReport)
    assert report.success
    assert report.passed_count >= 1


@pytest.mark.asyncio
async def test_existing_sandbox_behavior_unchanged(sandbox: CodeSandbox) -> None:
    """8. Existing non-GameDev sandbox behavior remains unchanged."""
    res = await sandbox.run_python("print('hello' + ' world')")
    assert res.success
    assert res.stdout.strip() == "hello world"

    # Test error in Python snippet
    err_res = await sandbox.run_python("raise ValueError('something went wrong')")
    assert not err_res.success
    assert "ValueError" in err_res.stderr


@pytest.mark.asyncio
async def test_safety_gates_cannot_be_bypassed(
    temp_workspace: WorkspaceManager, sandbox: CodeSandbox
) -> None:
    """9. Safety gates cannot be bypassed through GameDev tools."""
    # Policy with NO approval callback -> DESTRUCTIVE tools must fail closed
    unapproved_policy = SafetyPolicy(approval_callback=None)
    executor = ToolExecutor(unapproved_policy)
    agent = GameDevAgent()
    executor.register_gamedev_tools(agent, temp_workspace, sandbox)

    spec = GameProjectSpec(
        title="SafetyGame",
        genre=GameGenre.BOARD_GAME,
        target_engine=EngineTarget.PURE_CORE,
        target_language="python",
    )
    agent.scaffold(spec, temp_workspace, "safety_game")

    # SAFE tools succeed
    plan_res = await executor.execute("gamedev_plan", {"prompt": "Create a board game"})
    assert plan_res["success"]

    validate_res = await executor.execute("gamedev_validate", {"project_dir": "safety_game"})
    assert validate_res["success"]

    # DESTRUCTIVE tool (gamedev_verify) MUST fail closed without approval
    with pytest.raises(HITLRequiredError):
        await executor.execute("gamedev_verify", {"project_dir": "safety_game"})

    # When approved by callback, DESTRUCTIVE tool succeeds
    approved_policy = SafetyPolicy(approval_callback=lambda tool, args, desc: True)
    approved_executor = ToolExecutor(approved_policy)
    approved_executor.register_gamedev_tools(agent, temp_workspace, sandbox)

    verify_res = await approved_executor.execute("gamedev_verify", {"project_dir": "safety_game"})
    assert verify_res["success"]
    assert verify_res["passed_count"] >= 1
