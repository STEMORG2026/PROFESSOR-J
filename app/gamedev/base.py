"""GameEngineAdapter & EngineRegistry — Core abstractions for game engines.

Ensures PROFESSOR-J cognitive core is completely decoupled from engine-specific details
(Unity, Godot, Unreal, Pure Core, etc.).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from app.domain.gamedev import (
    EngineTarget,
    GameComponentSpec,
    GameProjectSpec,
    GameValidationReport,
)
from app.workspace.workspace import WorkspaceManager

logger = logging.getLogger(__name__)


class GameEngineAdapter(ABC):
    """Abstract interface for all game engine adapters."""

    @property
    @abstractmethod
    def engine_target(self) -> EngineTarget:
        """The engine or runtime targeted by this adapter."""
        ...

    @property
    @abstractmethod
    def supported_languages(self) -> tuple[str, ...]:
        """Supported programming languages (e.g. 'csharp', 'python')."""
        ...

    @abstractmethod
    def scaffold_project(
        self,
        spec: GameProjectSpec,
        workspace: WorkspaceManager,
        project_dir: str | None = None,
    ) -> list[str]:
        """Scaffold a new game project into the workspace.

        Args:
            spec: Project specification.
            workspace: Target workspace manager.
            project_dir: Optional relative subfolder in workspace.

        Returns:
            List of generated relative file paths.
        """
        ...

    @abstractmethod
    def generate_component(
        self,
        spec: GameComponentSpec,
        project: GameProjectSpec,
    ) -> dict[str, str]:
        """Generate code files for a specific game component.

        Returns:
            Dictionary mapping relative file paths to their generated source content.
        """
        ...

    @abstractmethod
    def validate_codebase(
        self,
        workspace: WorkspaceManager,
        project_dir: str,
    ) -> GameValidationReport:
        """Validate architectural compliance and domain purity of a game project."""
        ...

    @abstractmethod
    def get_build_command(self, project_dir: str) -> list[str]:
        """Return the CLI command to build the project."""
        ...

    @abstractmethod
    def get_test_command(self, project_dir: str) -> list[str]:
        """Return the CLI command to execute tests headlessly."""
        ...


class EngineRegistry:
    """Registry of available game engine adapters."""

    def __init__(self) -> None:
        self._adapters: dict[EngineTarget, GameEngineAdapter] = {}

    def register(self, adapter: GameEngineAdapter) -> None:
        """Register an engine adapter."""
        self._adapters[adapter.engine_target] = adapter
        logger.info("Registered GameEngineAdapter for %s", adapter.engine_target.value)

    def get(self, target: EngineTarget) -> GameEngineAdapter | None:
        """Get an adapter for the requested target."""
        return self._adapters.get(target)

    def require(self, target: EngineTarget) -> GameEngineAdapter:
        """Get an adapter or raise KeyError."""
        adapter = self._adapters.get(target)
        if adapter is None:
            raise KeyError(f"No GameEngineAdapter registered for target: {target.value}")
        return adapter

    def list_targets(self) -> list[EngineTarget]:
        """List all registered engine targets."""
        return list(self._adapters.keys())


__all__ = [
    "GameEngineAdapter",
    "EngineRegistry",
]
