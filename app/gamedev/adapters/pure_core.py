"""PureCoreAdapter — Engine adapter for headless, deterministic game rules.

Generates pure C# or Python game rule assemblies with zero engine coupling,
ready for headless test execution and integration into Unity, Godot, or custom clients.
"""

from __future__ import annotations

import logging

from app.domain.gamedev import (
    EngineTarget,
    GameArchitecturePattern,
    GameComponentSpec,
    GameProjectSpec,
    GameSystemType,
    GameValidationReport,
)
from app.gamedev.base import GameEngineAdapter
from app.gamedev.validator import GameArchitectureValidator
from app.workspace.workspace import WorkspaceManager

logger = logging.getLogger(__name__)


class PureCoreAdapter(GameEngineAdapter):
    """Engine adapter for Pure Core (headless rules) game development."""

    @property
    def engine_target(self) -> EngineTarget:
        return EngineTarget.PURE_CORE

    @property
    def supported_languages(self) -> tuple[str, ...]:
        return ("csharp", "python")

    def scaffold_project(
        self,
        spec: GameProjectSpec,
        workspace: WorkspaceManager,
        project_dir: str | None = None,
    ) -> list[str]:
        """Scaffold a pure core rules project in the workspace."""
        base_dir = (project_dir or spec.title.lower().replace(" ", "_")).strip("/")
        generated: list[str] = []

        is_csharp = spec.target_language.lower() == "csharp"

        # 1. Scaffolding README / Architecture manifest
        readme_content = f"""# {spec.title} — Pure Core Rules

> **Architecture:** Pure Core Rules ({spec.architecture_pattern.value})
> **Target Engine:** {spec.target_engine.value}
> **Determinism:** {'Strictly Deterministic' if spec.is_deterministic else 'Non-deterministic'}
> **Max Players:** {spec.max_players}

## Architecture Invariants
1. **Zero Engine Coupling**: Core rules have zero imports from presentation engines.
2. **Headless Execution**: Rules can be completely simulated and verified via unit tests in CI.
3. **Intent-Driven**: Client sends player intents; server/core calculates authoritative outcomes.
4. **Domain Events**: All state changes emit strongly typed events.

## Components
{chr(10).join(f"- **{c.name}** ({c.system_type.value}): {c.description}" for c in spec.components)}
"""
        readme_path = f"{base_dir}/README.md"
        workspace.write(readme_path, readme_content)
        generated.append(readme_path)

        if is_csharp:
            generated.extend(self._scaffold_csharp(spec, workspace, base_dir))
        else:
            generated.extend(self._scaffold_python(spec, workspace, base_dir))

        return generated

    def _scaffold_csharp(
        self, spec: GameProjectSpec, workspace: WorkspaceManager, base_dir: str
    ) -> list[str]:
        generated: list[str] = []

        # Core csproj
        csproj_content = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <RootNamespace>GameCore</RootNamespace>
  </PropertyGroup>
</Project>
"""
        csproj_path = f"{base_dir}/Core/GameCore.csproj"
        workspace.write(csproj_path, csproj_content)
        generated.append(csproj_path)

        # Core Contracts / Events
        contracts_content = """// Pure C# Domain Contracts — Zero UnityEngine / External I/O
namespace GameCore.Contracts;

public interface IGameIntent
{
    string PlayerId { get; }
    long TimestampTicks { get; }
}

public interface IDomainEvent
{
    string EventType { get; }
    long TimestampTicks { get; }
}

public enum GamePhase
{
    NotStarted,
    TurnActive,
    TurnResolving,
    GameOver
}
"""
        contracts_path = f"{base_dir}/Core/Contracts.cs"
        workspace.write(contracts_path, contracts_content)
        generated.append(contracts_path)

        # Generate each component
        for comp in spec.components:
            comp_files = self.generate_component(comp, spec)
            for rel_path, code in comp_files.items():
                full_path = f"{base_dir}/{rel_path}"
                workspace.write(full_path, code)
                generated.append(full_path)

        # Main GameState / Rules
        game_state_content = """namespace GameCore.Domain;

using GameCore.Contracts;

public sealed record GameState(
    string MatchId,
    int ActivePlayerIndex,
    GamePhase Phase,
    int TurnNumber,
    bool IsFinished,
    string? WinnerId
)
{
    public static GameState Initial(string matchId, int playerCount) =>
        new(matchId, 0, GamePhase.TurnActive, 1, false, null);
}
"""
        game_state_path = f"{base_dir}/Core/GameState.cs"
        workspace.write(game_state_path, game_state_content)
        generated.append(game_state_path)

        # Headless Test Suite
        test_content = """namespace GameCore.Tests;

using GameCore.Domain;
using GameCore.Contracts;

public class GameCoreTests
{
    public void InitialState_ShouldBeTurnActive()
    {
        var state = GameState.Initial("test-match", 2);
        if (state.Phase != GamePhase.TurnActive)
        {
            throw new System.Exception("Initial phase must be TurnActive");
        }
        if (state.ActivePlayerIndex != 0)
        {
            throw new System.Exception("Active player must start at index 0");
        }
    }
}
"""
        test_path = f"{base_dir}/Tests/GameCoreTests.cs"
        workspace.write(test_path, test_content)
        generated.append(test_path)

        return generated

    def _scaffold_python(
        self, spec: GameProjectSpec, workspace: WorkspaceManager, base_dir: str
    ) -> list[str]:
        generated: list[str] = []

        contracts_content = '''"""Pure Python Game Domain Contracts — Zero engine dependencies."""

from dataclasses import dataclass
from enum import Enum


class GamePhase(str, Enum):
    NOT_STARTED = "not_started"
    TURN_ACTIVE = "turn_active"
    TURN_RESOLVING = "turn_resolving"
    GAME_OVER = "game_over"


@dataclass(frozen=True, slots=True)
class GameState:
    match_id: str
    active_player_index: int
    phase: GamePhase
    turn_number: int
    is_finished: bool
    winner_id: str | None = None

    @classmethod
    def initial(cls, match_id: str, player_count: int = 2) -> "GameState":
        return cls(
            match_id=match_id,
            active_player_index=0,
            phase=GamePhase.TURN_ACTIVE,
            turn_number=1,
            is_finished=False,
            winner_id=None,
        )
'''
        contracts_path = f"{base_dir}/core/contracts.py"
        workspace.write(contracts_path, contracts_content)
        generated.append(contracts_path)

        # Generate each component
        for comp in spec.components:
            comp_files = self.generate_component(comp, spec)
            for rel_path, code in comp_files.items():
                full_path = f"{base_dir}/{rel_path}"
                workspace.write(full_path, code)
                generated.append(full_path)

        # Test suite
        test_content = '''"""Headless Unit Tests for Game Core Rules."""

from core.contracts import GamePhase, GameState


def test_initial_game_state() -> None:
    state = GameState.initial("test-123", 2)
    assert state.phase == GamePhase.TURN_ACTIVE
    assert state.active_player_index == 0
    assert not state.is_finished
'''
        test_path = f"{base_dir}/tests/test_rules.py"
        workspace.write(test_path, test_content)
        generated.append(test_path)

        return generated

    def generate_component(
        self,
        spec: GameComponentSpec,
        project: GameProjectSpec,
    ) -> dict[str, str]:
        """Generate code for a specific game component."""
        files: dict[str, str] = {}
        is_csharp = project.target_language.lower() == "csharp"

        if spec.system_type == GameSystemType.DICE_RNG:
            if is_csharp:
                files["Core/DiceRng.cs"] = """namespace GameCore.Systems;

using System;

public sealed class DiceRng
{
    private readonly Random _rng;

    public DiceRng(int seed)
    {
        _rng = new Random(seed);
    }

    public int Roll(int sides = 6)
    {
        if (sides < 1) throw new ArgumentOutOfRangeException(nameof(sides));
        return _rng.Next(1, sides + 1);
    }
}
"""
                files["Tests/DiceRngTests.cs"] = """namespace GameCore.Tests;

using GameCore.Systems;

public class DiceRngTests
{
    public void SeededRng_ShouldBeDeterministic()
    {
        var rng1 = new DiceRng(42);
        var rng2 = new DiceRng(42);

        for (int i = 0; i < 10; i++)
        {
            if (rng1.Roll() != rng2.Roll())
            {
                throw new System.Exception("Seeded rolls must be identical");
            }
        }
    }
}
"""
            else:
                files["core/dice_rng.py"] = '''"""Deterministic Dice RNG System."""

import random


class DiceRng:
    def __init__(self, seed: int = 42) -> None:
        self._rng = random.Random(seed)

    def roll(self, sides: int = 6) -> int:
        if sides < 1:
            raise ValueError("Sides must be >= 1")
        return self._rng.randint(1, sides)
'''
                files["tests/test_dice_rng.py"] = """from core.dice_rng import DiceRng


def test_seeded_dice_rng_determinism() -> None:
    r1 = DiceRng(42)
    r2 = DiceRng(42)
    assert [r1.roll() for _ in range(5)] == [r2.roll() for _ in range(5)]
"""

        elif spec.system_type == GameSystemType.TURN_MANAGER:
            if is_csharp:
                files["Core/TurnManager.cs"] = """namespace GameCore.Systems;

public sealed class TurnManager
{
    public int ActivePlayerIndex { get; private set; }
    public int PlayerCount { get; }
    public int TurnNumber { get; private set; } = 1;

    public TurnManager(int playerCount)
    {
        PlayerCount = playerCount > 0 ? playerCount : 2;
    }

    public void NextTurn()
    {
        ActivePlayerIndex = (ActivePlayerIndex + 1) % PlayerCount;
        if (ActivePlayerIndex == 0) TurnNumber++;
    }
}
"""
            else:
                files["core/turn_manager.py"] = '''"""Turn Manager System."""


class TurnManager:
    def __init__(self, player_count: int = 2) -> None:
        self.player_count = player_count
        self.active_player_index = 0
        self.turn_number = 1

    def next_turn(self) -> None:
        self.active_player_index = (self.active_player_index + 1) % self.player_count
        if self.active_player_index == 0:
            self.turn_number += 1
'''
        return files

    def validate_codebase(
        self,
        workspace: WorkspaceManager,
        project_dir: str,
    ) -> GameValidationReport:
        """Validate architectural compliance."""
        return GameArchitectureValidator.validate_workspace(
            workspace=workspace,
            project_dir=project_dir,
            pattern=GameArchitecturePattern.PURE_CORE_HEADLESS,
            target=EngineTarget.PURE_CORE,
        )

    def get_build_command(self, project_dir: str) -> list[str]:
        return ["dotnet", "build", project_dir]

    def get_test_command(self, project_dir: str) -> list[str]:
        return ["dotnet", "test", project_dir]


__all__ = ["PureCoreAdapter"]
