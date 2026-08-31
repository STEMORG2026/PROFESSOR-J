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
    def inventory(max_slots: int = 20, max_weight: float = 100.0) -> GameComponentSpec:
        """Create an inventory management component spec."""
        return GameComponentSpec(
            name="InventoryManager",
            system_type=GameSystemType.INVENTORY,
            description="Item storage, stacking, slot constraints, and equipment management.",
            pattern=GameArchitecturePattern.PURE_CORE_HEADLESS,
            parameters={"max_slots": max_slots, "max_weight": max_weight},
            dependencies=("EventBus",),
            source_files=("InventoryManager.cs",),
            test_files=("InventoryManagerTests.cs",),
        )

    @staticmethod
    def score_manager(initial_score: int = 0) -> GameComponentSpec:
        """Create a scoring and multiplier management component spec."""
        return GameComponentSpec(
            name="ScoreManager",
            system_type=GameSystemType.SCORING,
            description="Score tracking, combo multipliers, high scores, and leaderboards.",
            pattern=GameArchitecturePattern.PURE_CORE_HEADLESS,
            parameters={"initial_score": initial_score},
            dependencies=("EventBus",),
            source_files=("ScoreManager.cs",),
            test_files=("ScoreManagerTests.cs",),
        )

    @staticmethod
    def state_machine(initial_state: str = "NotStarted") -> GameComponentSpec:
        """Create a generic finite state machine component spec."""
        return GameComponentSpec(
            name="GameStateMachine",
            system_type=GameSystemType.STATE_MACHINE,
            description=(
                "Explicit hierarchical state machine with transition guards and event hooks."
            ),
            pattern=GameArchitecturePattern.STATE_MACHINE_EVENT_DRIVEN,
            parameters={"initial_state": initial_state},
            dependencies=("EventBus",),
            source_files=("GameStateMachine.cs",),
            test_files=("GameStateMachineTests.cs",),
        )

    @staticmethod
    def ai_minimax(depth: int = 3) -> GameComponentSpec:
        """Create a minimax AI decision engine component spec."""
        return GameComponentSpec(
            name="MinimaxAI",
            system_type=GameSystemType.AI_DECISION,
            description="Deterministic game tree lookahead AI evaluator with alpha-beta pruning.",
            pattern=GameArchitecturePattern.PURE_CORE_HEADLESS,
            parameters={"depth": depth},
            dependencies=("RulesEngine",),
            source_files=("MinimaxAI.cs",),
            test_files=("MinimaxAITests.cs",),
        )

    @staticmethod
    def save_state_manager(format_type: str = "json") -> GameComponentSpec:
        """Create a save state manager component spec."""
        return GameComponentSpec(
            name="SaveStateManager",
            system_type=GameSystemType.SAVE_STATE,
            description=(
                "Deterministic match serialization, snapshot restoration, and version migration."
            ),
            pattern=GameArchitecturePattern.PURE_CORE_HEADLESS,
            parameters={"format": format_type},
            dependencies=(),
            source_files=("SaveStateManager.cs",),
            test_files=("SaveStateManagerTests.cs",),
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
