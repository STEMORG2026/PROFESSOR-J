"""Game Architecture Patterns — Reusable architectural knowledge and constraints."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.gamedev import GameArchitecturePattern


@dataclass(frozen=True, slots=True)
class PatternDefinition:
    """Description and constraints of a game architecture pattern."""

    pattern: GameArchitecturePattern
    name: str
    description: str
    prohibited_core_imports: tuple[str, ...] = field(default_factory=tuple)
    required_layers: tuple[str, ...] = field(default_factory=tuple)
    key_principles: tuple[str, ...] = field(default_factory=tuple)


_PATTERNS: dict[GameArchitecturePattern, PatternDefinition] = {
    GameArchitecturePattern.PURE_CORE_HEADLESS: PatternDefinition(
        pattern=GameArchitecturePattern.PURE_CORE_HEADLESS,
        name="Pure Core Rules with Headless Testing",
        description=(
            "Game logic lives in a pure, zero-dependency rules domain. "
            "Engine (Unity/Godot/Unreal) handles presentation only. "
            "All state mutations occur via pure intent-processing functions and emit domain events."
        ),
        prohibited_core_imports=(
            "UnityEngine",
            "Godot",
            "Unreal",
            "pygame",
            "socket",
            "requests",
            "httpx",
            "tkinter",
        ),
        required_layers=("Core", "Tests", "Presentation"),
        key_principles=(
            "Zero engine imports in Core rules",
            "Headless determinism: tests run in CLI without opening engine",
            "Event-driven state changes: state mutations emit domain events",
            "Client sends intents; server/core calculates authoritative outcomes",
        ),
    ),
    GameArchitecturePattern.ECS: PatternDefinition(
        pattern=GameArchitecturePattern.ECS,
        name="Entity Component System",
        description=(
            "Data-oriented design separating entity identities, "
            "pure data components, and logic systems."
        ),
        prohibited_core_imports=(),
        required_layers=("Components", "Entities", "Systems"),
        key_principles=(
            "Components are pure data with no behavior",
            "Systems contain logic and operate on filtered component tuples",
            "Cache-friendly data layout",
        ),
    ),
    GameArchitecturePattern.STATE_MACHINE_EVENT_DRIVEN: PatternDefinition(
        pattern=GameArchitecturePattern.STATE_MACHINE_EVENT_DRIVEN,
        name="Event-Driven State Machine",
        description=(
            "Hierarchical or flat state machine driven by an " "asynchronous/synchronous event bus."
        ),
        prohibited_core_imports=(),
        required_layers=("States", "Events", "Transitions", "Context"),
        key_principles=(
            "Discrete states with explicit entry/exit/update lifecycle",
            "Transitions triggered strictly by strongly-typed events",
        ),
    ),
    GameArchitecturePattern.MODEL_VIEW_PRESENTER: PatternDefinition(
        pattern=GameArchitecturePattern.MODEL_VIEW_PRESENTER,
        name="Model-View-Presenter for Games",
        description=(
            "Model holds authoritative state, View handles visuals/audio, " "Presenter coordinates."
        ),
        prohibited_core_imports=("UnityEngine", "Godot", "Unreal"),
        required_layers=("Model", "View", "Presenter"),
        key_principles=(
            "Model has zero reference to View",
            "Presenter mediates user actions from View to Model",
        ),
    ),
}


class GamePatternCatalog:
    """Catalog for game architecture patterns."""

    @staticmethod
    def get_pattern(pattern: GameArchitecturePattern) -> PatternDefinition:
        """Get definition for an architecture pattern."""
        return _PATTERNS.get(
            pattern,
            PatternDefinition(
                pattern=pattern,
                name=pattern.value,
                description="Standard game architecture pattern.",
            ),
        )

    @staticmethod
    def list_patterns() -> list[PatternDefinition]:
        """List all available pattern definitions."""
        return list(_PATTERNS.values())


__all__ = [
    "PatternDefinition",
    "GamePatternCatalog",
]
