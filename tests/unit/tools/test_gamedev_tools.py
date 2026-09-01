"""Unit tests for GameDev tools in ToolExecutor."""

import tempfile
from collections.abc import Generator

import pytest

from app.gamedev.agent import GameDevAgent
from app.guardrails.policy import SafetyPolicy
from app.tools.executor import ToolExecutor
from app.workspace.workspace import WorkspaceManager


@pytest.fixture
def temp_workspace() -> Generator[WorkspaceManager, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield WorkspaceManager(tmpdir)


@pytest.mark.asyncio
async def test_gamedev_tools_execution(temp_workspace: WorkspaceManager) -> None:
    policy = SafetyPolicy(approval_callback=None)
    executor = ToolExecutor(policy)
    agent = GameDevAgent()

    executor.register_gamedev_tools(agent, temp_workspace)

    assert executor.has_tool("gamedev_plan")
    assert executor.has_tool("gamedev_scaffold")
    assert executor.has_tool("gamedev_validate")

    # 1. Execute plan tool
    plan_res = await executor.execute(
        "gamedev_plan", {"prompt": "Create a turn-based board game with dice mechanics"}
    )
    assert plan_res["success"]
    assert "DiceRNG" in plan_res["components"]
    assert "TurnManager" in plan_res["components"]

    # 2. Execute scaffold tool
    scaffold_res = await executor.execute(
        "gamedev_scaffold",
        {
            "prompt": "Create a turn-based board game with dice mechanics",
            "project_dir": "test_game",
        },
    )
    assert scaffold_res["success"]
    assert len(scaffold_res["generated_files"]) > 0

    # 3. Execute validate tool
    val_res = await executor.execute("gamedev_validate", {"project_dir": "test_game"})
    assert val_res["success"]
    assert val_res["is_valid"]
