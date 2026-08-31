"""GameDevAgent — Orchestrates game architecture planning, scaffolding, and validation."""

from __future__ import annotations

import logging
import re
from typing import Any

from app.domain.gamedev import (
    EngineTarget,
    GameArchitecturePattern,
    GameComponentSpec,
    GameGenre,
    GameProjectSpec,
    GameValidationReport,
)
from app.gamedev.adapters.pure_core import PureCoreAdapter
from app.gamedev.base import EngineRegistry
from app.gamedev.components import GameComponentCatalog
from app.workspace.workspace import WorkspaceManager

logger = logging.getLogger(__name__)


class GameDevAgent:
    """Specialized agent for game development capabilities."""

    def __init__(self, registry: EngineRegistry | None = None) -> None:
        self.registry = registry or self._default_registry()

    @staticmethod
    def _default_registry() -> EngineRegistry:
        reg = EngineRegistry()
        reg.register(PureCoreAdapter())
        return reg

    def plan_project(
        self,
        prompt: str,
        target: EngineTarget = EngineTarget.PURE_CORE,
        target_language: str = "csharp",
    ) -> GameProjectSpec:
        """Formulate a structured GameProjectSpec from a natural language prompt."""
        low = prompt.lower()

        # Genre detection
        genre = GameGenre.BOARD_GAME
        if "strategy" in low or "tactics" in low:
            genre = GameGenre.TURN_BASED_STRATEGY
        elif "puzzle" in low:
            genre = GameGenre.PUZZLE
        elif "arcade" in low:
            genre = GameGenre.ARCADE
        elif "rpg" in low:
            genre = GameGenre.RPG
        elif "stem" in low or "education" in low or "physics" in low:
            genre = GameGenre.EDUCATIONAL_STEM

        # Target engine detection from prompt if present
        if "unity" in low:
            target = EngineTarget.UNITY
        elif "godot" in low:
            target = EngineTarget.GODOT
        elif "unreal" in low:
            target = EngineTarget.UNREAL

        # Extract player count if mentioned
        player_match = re.search(r"(\d+)\s*(?:players?|player)", low)
        max_players = int(player_match.group(1)) if player_match else 2

        # Extract title or formulate default
        title = "DeterministicGameCore"
        if "ludo" in low:
            title = "LudoRulesCore"
        elif "chess" in low:
            title = "ChessRulesCore"
        elif "tic tac toe" in low or "tictactoe" in low:
            title = "TicTacToeCore"

        # Build components
        components: list[GameComponentSpec] = [
            GameComponentCatalog.event_bus(),
            GameComponentCatalog.turn_manager(player_count=max_players),
        ]

        if "dice" in low or "rng" in low or "random" in low or "ludo" in low:
            components.append(GameComponentCatalog.dice_rng(dice_count=1, sides=6))

        if "grid" in low or "board" in low or "tile" in low:
            components.append(GameComponentCatalog.grid_board(width=15, height=15))

        components.append(GameComponentCatalog.rules_engine(f"{title}Rules"))

        return GameProjectSpec(
            title=title,
            genre=genre,
            target_engine=target,
            architecture_pattern=GameArchitecturePattern.PURE_CORE_HEADLESS,
            description=prompt,
            components=tuple(components),
            target_language=target_language,
            max_players=max_players,
            is_deterministic=True,
        )

    def scaffold(
        self,
        spec: GameProjectSpec,
        workspace: WorkspaceManager,
        project_dir: str | None = None,
    ) -> dict[str, Any]:
        """Scaffold project via the appropriate engine adapter and validate."""
        # Fallback to PURE_CORE if requested target adapter is not yet registered
        adapter = self.registry.get(spec.target_engine)
        if adapter is None:
            logger.warning(
                "Adapter for %s not found, falling back to PURE_CORE", spec.target_engine.value
            )
            adapter = self.registry.require(EngineTarget.PURE_CORE)

        target_dir = project_dir or spec.title.lower().replace(" ", "_")
        generated_files = adapter.scaffold_project(spec, workspace, target_dir)
        validation_report = adapter.validate_codebase(workspace, target_dir)

        return {
            "success": True,
            "project_id": spec.project_id,
            "title": spec.title,
            "target_engine": spec.target_engine.value,
            "architecture_pattern": spec.architecture_pattern.value,
            "generated_files": generated_files,
            "validation": {
                "is_valid": validation_report.is_valid,
                "summary": validation_report.summary,
                "error_count": validation_report.error_count,
                "warning_count": validation_report.warning_count,
            },
        }

    def validate(
        self,
        workspace: WorkspaceManager,
        project_dir: str,
        target: EngineTarget = EngineTarget.PURE_CORE,
    ) -> GameValidationReport:
        """Validate an existing game project in workspace."""
        adapter = self.registry.get(target) or self.registry.require(EngineTarget.PURE_CORE)
        return adapter.validate_codebase(workspace, project_dir)


__all__ = ["GameDevAgent"]
