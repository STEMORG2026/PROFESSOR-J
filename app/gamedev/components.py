"""Reusable Game Components Catalog — Specifications and contracts for common game systems."""

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
            purpose="Generate deterministic pseudo-random integer values seeded per match.",
            inputs=("sides: int", "count: int"),
            outputs=("roll_result: int",),
            state_fields=("_seed: int", "_roll_count: int"),
            emitted_events=("DiceRolledEvent",),
            invariants=(
                "Roll results are strictly between 1 and sides inclusive.",
                "Given identical initial seed, roll sequence is 100% reproducible.",
            ),
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
            purpose="Orchestrate round-robin player turn rotation and phase transitions.",
            inputs=("next_turn_intent",),
            outputs=("active_player: int", "turn_number: int"),
            state_fields=("active_player: int", "turn_number: int", "player_count: int"),
            emitted_events=("TurnAdvancedEvent", "PhaseChangedEvent"),
            invariants=(
                "Active player index is always in [0, player_count - 1].",
                "Turn number increments when rotating back to player 0.",
            ),
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
            purpose="Manage 2D spatial coordinates, distance metrics, and boundary validation.",
            inputs=("x: int", "y: int"),
            outputs=("is_valid: bool", "tile_occupant: int | None"),
            state_fields=("width: int", "height: int", "occupancy_map: dict"),
            emitted_events=("TileOccupiedEvent", "TileClearedEvent"),
            invariants=(
                "Coordinates outside [0, width-1] x [0, height-1] are rejected as out of bounds.",
                "Manhattan distance is calculated as |x1 - x2| + |y1 - y2|.",
            ),
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
            purpose="Publish and subscribe to immutable domain events synchronously in memory.",
            inputs=("event: IDomainEvent", "listener: Callable"),
            outputs=(),
            state_fields=("_listeners: dict",),
            emitted_events=(),
            invariants=(
                "Events are dispatched synchronously in publication order.",
                "Subscribers cannot mutate event payloads.",
            ),
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
            purpose="Enforce authoritative game rules and evaluate legal moves & win states.",
            inputs=("intent: IGameIntent", "state: GameState"),
            outputs=("result: MoveResult", "is_game_over: bool", "winner: int | None"),
            state_fields=("rules_config: dict",),
            emitted_events=("MoveValidatedEvent", "GameOverEvent"),
            invariants=(
                "Illegal player moves are rejected without mutating match state.",
                "Win conditions are evaluated authoritatively following each valid move.",
            ),
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
            purpose="Manage item storage, stack limits, capacity constraints, and equipment.",
            inputs=("item_id: str", "quantity: int", "slot_index: int | None"),
            outputs=("success: bool", "remaining_slots: int", "current_weight: float"),
            state_fields=("slots: list", "max_slots: int", "max_weight: float"),
            emitted_events=("ItemAddedEvent", "ItemRemovedEvent", "InventoryFullEvent"),
            invariants=(
                "Total allocated item slots cannot exceed max_slots.",
                "Item quantities must be strictly positive integers (quantity >= 1).",
                "Removing items fails if requested quantity exceeds available count.",
            ),
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
            purpose="Track player scores, streak multipliers, and high score leaderboards.",
            inputs=("points: int", "player_id: int", "multiplier: float"),
            outputs=("current_score: int",),
            state_fields=("scores: dict[int, int]", "multipliers: dict[int, float]"),
            emitted_events=("ScoreUpdatedEvent", "HighScoreAchievedEvent"),
            invariants=(
                "Scores are non-negative integers.",
                "Points awarded are modified by the active combo multiplier.",
            ),
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
            purpose="Maintain explicit phase transitions and guard against invalid intent timings.",
            inputs=("transition_trigger: str",),
            outputs=("current_state: str", "is_transition_valid: bool"),
            state_fields=("current_state: str", "valid_transitions: dict"),
            emitted_events=("StateTransitionedEvent",),
            invariants=(
                "Transitions must be explicitly declared in the transition graph.",
                "Guards must evaluate to True before state transition completes.",
            ),
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
            purpose="Evaluate game tree lookahead to select optimal deterministic bot actions.",
            inputs=("state: GameState", "depth: int"),
            outputs=("best_intent: IGameIntent", "eval_score: float"),
            state_fields=("search_depth: int", "eval_weights: dict"),
            emitted_events=("AIDecisionFormulatedEvent",),
            invariants=(
                "AI operates on state clones without side effects on active match state.",
                "Outputs the intent with the highest heuristic minimax score.",
            ),
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
            purpose="Serialize and deserialize match state snapshots with schema versioning.",
            inputs=("state: GameState", "snapshot_str: str"),
            outputs=("snapshot_dict: dict", "restored_state: GameState"),
            state_fields=("schema_version: int", "format: str"),
            emitted_events=("StateSavedEvent", "StateRestoredEvent"),
            invariants=(
                "Serializing and immediately deserializing yields an identical state object.",
                "Snapshots must include an explicit schema_version field.",
            ),
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
