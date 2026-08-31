"""Unit tests for GameDevAgent."""

import tempfile
from collections.abc import Generator

import pytest

from app.domain.gamedev import EngineTarget, GameGenre, GameSystemType
from app.gamedev.agent import GameDevAgent
from app.workspace.workspace import WorkspaceManager


@pytest.fixture
def temp_workspace() -> Generator[WorkspaceManager, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield WorkspaceManager(tmpdir)


def test_agent_plan_project() -> None:
    agent = GameDevAgent()
    spec = agent.plan_project("Create a turn-based board game with dice mechanics for 4 players")

    assert spec.genre == GameGenre.BOARD_GAME
    assert spec.target_engine == EngineTarget.PURE_CORE
    assert spec.max_players == 4
    assert spec.has_system(GameSystemType.DICE_RNG)
    assert spec.has_system(GameSystemType.TURN_MANAGER)
    assert spec.has_system(GameSystemType.EVENT_BUS)


def test_agent_scaffold_and_validate(temp_workspace: WorkspaceManager) -> None:
    agent = GameDevAgent()
    spec = agent.plan_project("Create a turn-based board game with dice mechanics for 2 players")

    result = agent.scaffold(spec, temp_workspace, "my_board_game")
    assert result["success"]
    assert result["title"] == spec.title
    assert len(result["generated_files"]) > 0
    assert result["validation"]["is_valid"]
    assert result["validation"]["error_count"] == 0

    # Validate directly
    report = agent.validate(temp_workspace, "my_board_game")
    assert report.is_valid
