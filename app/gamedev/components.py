"""Reusable Game Components Catalog — Specifications and templates for common game systems."""

from __future__ import annotations

from app.domain.gamedev import GameArchitecturePattern, GameComponentSpec, GameSystemType


class GameComponentCatalog:
    """Catalog of standard, reusable game component specifications."""

    @staticmethod
    def dice_rng(
        dice_count: int = 1, sides: int = 6, deterministic: bool = True
    ) -> GameComponentSpec:
        """Create a deterministic dice RNG component spec."""
        return GameComponentSpec(
            name="DiceRNG",
            system_type=GameSystemType.DICE_RNG,
            description="Deterministic pseudo-random dice rolling system with seed support.",
            pattern=GameArchitecturePattern.PURE_CORE_HEADLESS,
            parameters={
                "dice_count": dice_count,
                "sides": sides,
                "deterministic": deterministic,
            },
            source_files=("DiceRng.cs",),
            test_files=("DiceRngTests.cs",),
        )

    @staticmethod
    def turn_manager(player_count: int = 2, max_turns: int | None = None) -> GameComponentSpec:
        """Create a turn management component spec."""
        return GameComponentSpec(
            name="TurnManager",
            system_type=GameSystemType.TURN_MANAGER,
            description="Turn order orchestrator managing player phases and turn transitions.",
            pattern=GameArchitecturePattern.PURE_CORE_HEADLESS,
            parameters={
                "player_count": player_count,
                "max_turns": max_turns,
            },
            dependencies=("EventBus",),
            source_files=("TurnManager.cs",),
            test_files=("TurnManagerTests.cs",),
        )

    @staticmethod
    def grid_board(width: int = 15, height: int = 15) -> GameComponentSpec:
        """Create a 2D grid/board component spec."""
        return GameComponentSpec(
            name="GridBoard",
            system_type=GameSystemType.GRID_BOARD,
            description="2D coordinate board system with tile indexing and occupancy state.",
            pattern=GameArchitecturePattern.PURE_CORE_HEADLESS,
            parameters={
                "width": width,
                "height": height,
            },
            source_files=("GridBoard.cs",),
            test_files=("GridBoardTests.cs",),
        )

    @staticmethod
    def event_bus() -> GameComponentSpec:
        """Create a domain event bus component spec."""
        return GameComponentSpec(
            name="EventBus",
            system_type=GameSystemType.EVENT_BUS,
            description="Pure in-memory synchronous event bus for domain event propagation.",
            pattern=GameArchitecturePattern.PURE_CORE_HEADLESS,
            parameters={},
            source_files=("GameEventBus.cs",),
            test_files=("GameEventBusTests.cs",),
        )

    @staticmethod
    def rules_engine(rule_name: str = "StandardGameRules") -> GameComponentSpec:
        """Create a pure rules engine component spec."""
        return GameComponentSpec(
            name=rule_name,
            system_type=GameSystemType.RULES_ENGINE,
            description="Authoritative game rules validator evaluating moves and win conditions.",
            pattern=GameArchitecturePattern.PURE_CORE_HEADLESS,
            parameters={"rule_name": rule_name},
            dependencies=("EventBus", "TurnManager"),
            source_files=(f"{rule_name}.cs",),
            test_files=(f"{rule_name}Tests.cs",),
        )

    @staticmethod
    def get_default_board_game_components(player_count: int = 2) -> tuple[GameComponentSpec, ...]:
        """Return the standard set of components for a turn-based board game."""
        return (
            GameComponentCatalog.event_bus(),
            GameComponentCatalog.dice_rng(dice_count=1, sides=6),
            GameComponentCatalog.turn_manager(player_count=player_count),
            GameComponentCatalog.grid_board(width=15, height=15),
            GameComponentCatalog.rules_engine("BoardGameRules"),
        )


__all__ = ["GameComponentCatalog"]
