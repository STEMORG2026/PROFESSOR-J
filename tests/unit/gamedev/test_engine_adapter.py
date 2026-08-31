"""Unit tests for GameEngineAdapter and PureCoreAdapter."""

import tempfile
from collections.abc import Generator

import pytest

from app.domain.gamedev import EngineTarget, GameGenre, GameProjectSpec
from app.gamedev.adapters.pure_core import PureCoreAdapter
from app.gamedev.base import EngineRegistry
from app.gamedev.components import GameComponentCatalog
from app.workspace.workspace import WorkspaceManager


@pytest.fixture
def temp_workspace() -> Generator[WorkspaceManager, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield WorkspaceManager(tmpdir)


def test_engine_registry() -> None:
    reg = EngineRegistry()
    adapter = PureCoreAdapter()
    reg.register(adapter)

    assert reg.get(EngineTarget.PURE_CORE) == adapter
    assert reg.require(EngineTarget.PURE_CORE) == adapter
    assert reg.get(EngineTarget.UNITY) is None
    assert EngineTarget.PURE_CORE in reg.list_targets()

    with pytest.raises(KeyError):
        reg.require(EngineTarget.UNITY)


def test_pure_core_adapter_scaffold_csharp(temp_workspace: WorkspaceManager) -> None:
    adapter = PureCoreAdapter()
    spec = GameProjectSpec(
        title="LudoCore",
        genre=GameGenre.BOARD_GAME,
        target_engine=EngineTarget.PURE_CORE,
        target_language="csharp",
        components=(
            GameComponentCatalog.event_bus(),
            GameComponentCatalog.dice_rng(),
            GameComponentCatalog.turn_manager(player_count=4),
        ),
    )

    generated = adapter.scaffold_project(spec, temp_workspace, "ludo_core")
    assert len(generated) >= 5
    assert "ludo_core/README.md" in generated
    assert "ludo_core/Core/GameCore.csproj" in generated
    assert "ludo_core/Core/Contracts.cs" in generated
    assert "ludo_core/Core/GameState.cs" in generated
    assert "ludo_core/Core/DiceRng.cs" in generated
    assert "ludo_core/Tests/GameCoreTests.cs" in generated

    # Verify content
    readme = temp_workspace.read("ludo_core/README.md")["content"]
    assert "Pure Core Rules" in readme

    contracts = temp_workspace.read("ludo_core/Core/Contracts.cs")["content"]
    assert "IGameIntent" in contracts

    # Verify build / test commands
    assert adapter.get_build_command("ludo_core") == ["dotnet", "build", "ludo_core"]
    assert adapter.get_test_command("ludo_core") == ["dotnet", "test", "ludo_core"]


def test_pure_core_adapter_scaffold_python(temp_workspace: WorkspaceManager) -> None:
    adapter = PureCoreAdapter()
    spec = GameProjectSpec(
        title="PythonChess",
        genre=GameGenre.BOARD_GAME,
        target_engine=EngineTarget.PURE_CORE,
        target_language="python",
        components=(
            GameComponentCatalog.dice_rng(),
            GameComponentCatalog.turn_manager(player_count=2),
        ),
    )

    generated = adapter.scaffold_project(spec, temp_workspace, "chess_core")
    assert len(generated) >= 4
    assert "chess_core/core/contracts.py" in generated
    assert "chess_core/tests/test_rules.py" in generated

    contracts = temp_workspace.read("chess_core/core/contracts.py")["content"]
    assert "GameState" in contracts
