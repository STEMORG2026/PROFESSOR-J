import tempfile
from collections.abc import Generator
from pathlib import Path

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
    assert "test_deliberate_failure" in report.failed_tests
    assert len(report.failure_details) >= 1


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


@pytest.mark.asyncio
async def test_dangerous_arguments_rejected_in_sandbox(sandbox: CodeSandbox) -> None:
    """10. Dangerous argument injection is rejected by sandbox validator."""
    # 1. Reject python -c arbitrary execution
    res1 = await sandbox.run_command(["python3", "-c", "import os; print('hacked')"], cwd="/tmp")  # nosec B108
    assert not res1.success
    assert "Python in sandbox is only permitted with -m module invocation" in res1.stderr

    # 2. Reject unapproved python modules
    res2 = await sandbox.run_command(["python3", "-m", "pip", "install", "pwned"], cwd="/tmp")  # nosec B108
    assert not res2.success
    assert "Python module 'pip' is not an approved sandbox runner" in res2.stderr

    # 3. Reject unapproved dotnet subcommands
    res3 = await sandbox.run_command(["dotnet", "tool", "install", "something"], cwd="/tmp")  # nosec B108
    assert not res3.success
    assert "dotnet subcommand 'tool' is not permitted" in res3.stderr

    # 4. Reject dangerous flags
    res4 = await sandbox.run_command(
        ["python3", "-m", "pytest", "--override-ini=bad"],
        cwd="/tmp",  # nosec B108
    )
    assert not res4.success
    assert "is not permitted in sandbox" in res4.stderr and "--override-ini" in res4.stderr

    # 5. Reject null bytes
    res5 = await sandbox.run_command(["python3", "-m", "pytest", "arg\x00evil"], cwd="/tmp")  # nosec B108
    assert not res5.success
    assert "Null byte detected" in res5.stderr


def test_symlink_path_escape_rejected_in_workspace(temp_workspace: WorkspaceManager) -> None:
    """11. Symlink escape outside workspace is rejected."""
    with tempfile.TemporaryDirectory() as outside_dir:
        outside_file = Path(outside_dir) / "secret.txt"
        outside_file.write_text("topsecret", encoding="utf-8")

        # Create symlink inside workspace pointing to outside directory
        symlink_path = temp_workspace.root / "symlink_outside"
        try:
            symlink_path.symlink_to(outside_dir, target_is_directory=True)
        except OSError:
            pytest.skip("Symlink creation not permitted in this test environment")

        # Resolving relative path through symlink must raise WorkspaceSecurityError
        with pytest.raises(WorkspaceSecurityError):
            temp_workspace._resolve("symlink_outside/secret.txt")

        # Reading file through symlink must raise WorkspaceSecurityError
        with pytest.raises(WorkspaceSecurityError):
            temp_workspace.read("symlink_outside/secret.txt")


@pytest.mark.asyncio
async def test_csharp_test_failure_parsing() -> None:
    """12. Structured parsing of C# dotnet test failures for autonomous repair."""
    adapter = PureCoreAdapter()

    mock_dotnet_fail = """
  GameCore -> /workspace/ludo/bin/Debug/net8.0/GameCore.dll
  GameCoreTests -> /workspace/ludo/bin/Debug/net8.0/GameCoreTests.dll
Test run for /workspace/ludo/bin/Debug/net8.0/GameCoreTests.dll (.NETCoreApp,Version=v8.0)

  Failed GameCoreTests.InitialState_ShouldBeTurnActive [15 ms]
  Error Message:
   System.Exception: Initial phase must be TurnActive
  Stack Trace:
     at GameCoreTests.InitialState_ShouldBeTurnActive() in Tests/GameCoreTests.cs:line 12

Failed!  - Failed:     1, Passed:     3, Skipped:     0, Total:     4, Duration: 42 ms
"""
    result = SandboxResult(
        success=False,
        stdout=mock_dotnet_fail,
        stderr="",
        exit_code=1,
        timed_out=False,
        duration_ms=45.0,
    )

    report = adapter.parse_test_output(result)
    assert not report.success
    assert report.passed_count == 3
    assert report.failed_count == 1
    assert "GameCoreTests.InitialState_ShouldBeTurnActive" in report.failed_tests
    assert len(report.failure_details) == 1
    assert report.failure_details[0]["test_name"] == "GameCoreTests.InitialState_ShouldBeTurnActive"
    assert report.failure_details[0]["framework"] == "dotnet"
