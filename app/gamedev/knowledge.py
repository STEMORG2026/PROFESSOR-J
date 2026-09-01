"""Game Development Knowledge Base — Structured, queryable engineering knowledge.

Provides actionable architectural rules, state invariants, anti-patterns, and testing
strategies for the GameDev capability during planning, implementation, and repair.
"""

from __future__ import annotations

import logging

from app.domain.gamedev import (
    GameArchitecturePattern,
    GameKnowledgeCategory,
    GameKnowledgeTopic,
)

logger = logging.getLogger(__name__)


class GameKnowledgeCatalog:
    """Catalog of structured game engineering knowledge topics."""

    def __init__(self, custom_topics: tuple[GameKnowledgeTopic, ...] = ()) -> None:
        self._topics: dict[str, GameKnowledgeTopic] = {}
        for topic in self._default_topics() + custom_topics:
            self._topics[topic.topic_id] = topic

    def get(self, topic_id: str) -> GameKnowledgeTopic | None:
        """Retrieve a knowledge topic by identifier."""
        return self._topics.get(topic_id)

    def require(self, topic_id: str) -> GameKnowledgeTopic:
        """Retrieve a topic or raise ValueError."""
        topic = self.get(topic_id)
        if topic is None:
            raise ValueError(f"Game knowledge topic '{topic_id}' not found in catalog.")
        return topic

    def list_by_category(self, category: GameKnowledgeCategory) -> tuple[GameKnowledgeTopic, ...]:
        """List all topics under a specific category."""
        return tuple(t for t in self._topics.values() if t.category == category)

    def get_by_category(self, category: GameKnowledgeCategory) -> tuple[GameKnowledgeTopic, ...]:
        """Alias for list_by_category."""
        return self.list_by_category(category)

    def search(self, query: str) -> tuple[GameKnowledgeTopic, ...]:
        """Search topics by keyword matching across tags, summary, and name."""
        tokens = set(query.lower().split())
        matched: list[tuple[int, GameKnowledgeTopic]] = []

        for topic in self._topics.values():
            score = 0
            # Tag match
            score += sum(3 for t in topic.tags if any(tok in t.lower() for tok in tokens))
            # Name match
            score += sum(2 for tok in tokens if tok in topic.name.lower())
            # Category match
            score += sum(2 for tok in tokens if tok in topic.category.value.lower())
            # Summary match
            score += sum(1 for tok in tokens if tok in topic.summary.lower())

            if score > 0:
                matched.append((score, topic))

        matched.sort(key=lambda x: x[0], reverse=True)
        return tuple(t for _, t in matched)

    def all_topics(self) -> tuple[GameKnowledgeTopic, ...]:
        """Return all registered knowledge topics."""
        return tuple(self._topics.values())

    @staticmethod
    def _default_topics() -> tuple[GameKnowledgeTopic, ...]:
        return (
            GameKnowledgeTopic(
                topic_id="pure_core_presentation_separation",
                name="Pure Core Presentation Separation",
                category=GameKnowledgeCategory.ARCHITECTURE,
                summary=(
                    "Game rules, state mutations, and win conditions must live in a pure, "
                    "headless Core domain assembly with zero presentation engine imports."
                ),
                key_invariants=(
                    "GameCore contains zero imports of UnityEngine, Godot, Unreal, or GUI libs.",
                    "All game state mutations are executed via pure, deterministic functions.",
                    "Presentation layers consume domain events and never mutate state directly.",
                ),
                anti_patterns=(
                    "Importing UnityEngine.MonoBehaviour inside GameCore.",
                    "Calling presentation APIs (e.g. Debug.Log, AudioSource) from rules code.",
                    "Embedding player state inside UI controller components.",
                ),
                recommended_patterns=(
                    GameArchitecturePattern.PURE_CORE_HEADLESS,
                    GameArchitecturePattern.MODEL_VIEW_PRESENTER,
                ),
                testing_strategy=(
                    "Run 100% headless unit tests using standard test runners (NUnit / pytest)."
                ),
                tags=("pure_core", "headless", "presentation_separation", "domain_purity"),
            ),
            GameKnowledgeTopic(
                topic_id="game_loop_determinism",
                name="Deterministic Game Loops & RNG",
                category=GameKnowledgeCategory.STATE_MANAGEMENT,
                summary=(
                    "Game simulation must be 100% reproducible given identical initial seeds "
                    "and player intents."
                ),
                key_invariants=(
                    "Given initial State(S0) and intents [I1..In], State(Sn) is reproducible.",
                    "RNG must be explicitly seeded and isolated per match or subsystem.",
                    "State updates must be side-effect free and return immutable state snapshots.",
                ),
                anti_patterns=(
                    "Using system clock (DateTime.Now) inside rules evaluation.",
                    "Unseeded static global random generators.",
                    "Mutating shared state across concurrent threads without locks.",
                ),
                recommended_patterns=(
                    GameArchitecturePattern.PURE_CORE_HEADLESS,
                    GameArchitecturePattern.STATE_MACHINE_EVENT_DRIVEN,
                ),
                testing_strategy=(
                    "Run identical intent sequences across randomized seeds and assert checksums."
                ),
                tags=("determinism", "game_loop", "rng", "reproducibility", "tick"),
            ),
            GameKnowledgeTopic(
                topic_id="state_machine_fsm",
                name="Hierarchical Finite State Machines",
                category=GameKnowledgeCategory.STATE_MANAGEMENT,
                summary=(
                    "Game lifecycle and turn phases governed by explicit states, guards, "
                    "and transition events."
                ),
                key_invariants=(
                    "Every phase transition (NotStarted -> Active -> GameOver) must be guarded.",
                    "Invalid player intents in the wrong phase must be rejected as illegal moves.",
                    "State transitions emit domain events to notify presentation listeners.",
                ),
                anti_patterns=(
                    "Boolean flag soup (e.g. isRolling, isMoving, hasWon) instead of enum states.",
                    "Implicit transitions hidden in nested conditional branches.",
                ),
                recommended_patterns=(
                    GameArchitecturePattern.STATE_MACHINE_EVENT_DRIVEN,
                    GameArchitecturePattern.PURE_CORE_HEADLESS,
                ),
                testing_strategy=(
                    "Test invalid transition attempts; verify guards reject out-of-turn intents."
                ),
                tags=("fsm", "state_machine", "turn_lifecycle", "guards", "phases"),
            ),
            GameKnowledgeTopic(
                topic_id="grid_spatial_indexing",
                name="2D Grid & Board Spatial Management",
                category=GameKnowledgeCategory.GAMEPLAY_SYSTEMS,
                summary=(
                    "Board game tiles, coordinates, paths, and token placements managed "
                    "via spatial indexing."
                ),
                key_invariants=(
                    "Coordinates must enforce boundary validation [0, width) x [0, height).",
                    "Token movement calculates discrete tile offsets rather than world vectors.",
                    "Safe zones and tracks must be represented as structured path nodes.",
                ),
                anti_patterns=(
                    "Using Unity Raycasts or world positions to determine tile occupancy.",
                    "Hardcoded tile index magic numbers without named constants.",
                ),
                recommended_patterns=(
                    GameArchitecturePattern.PURE_CORE_HEADLESS,
                    GameArchitecturePattern.ECS,
                ),
                testing_strategy=(
                    "Boundary tests for (0,0), (max_x, max_y), out-of-bounds, and path wrap-around."
                ),
                tags=("grid", "board", "spatial", "coordinates", "movement"),
            ),
            GameKnowledgeTopic(
                topic_id="inventory_invariants",
                name="Inventory & Item Constraints",
                category=GameKnowledgeCategory.GAMEPLAY_SYSTEMS,
                summary=(
                    "Item management, stacking, slot limits, and weight bounds governed "
                    "by deterministic capacity rules."
                ),
                key_invariants=(
                    "Total slot count must never exceed maximum configured capacity.",
                    "Item quantities must be strictly positive integers (quantity >= 1).",
                    "Removing items fails if requested quantity exceeds current stock.",
                    "Stacking items cannot exceed max_stack limit per slot.",
                ),
                anti_patterns=(
                    "Negative item counts or floating point quantities.",
                    "Silently dropping items on overflow without raising explicit capacity error.",
                ),
                recommended_patterns=(
                    GameArchitecturePattern.PURE_CORE_HEADLESS,
                    GameArchitecturePattern.STATE_MACHINE_EVENT_DRIVEN,
                ),
                testing_strategy=(
                    "Capacity boundary tests: add to full inventory, stack overflow, underflow."
                ),
                tags=("inventory", "items", "capacity", "stacking", "equipment"),
            ),
            GameKnowledgeTopic(
                topic_id="state_schema_evolution",
                name="Game State Schema Evolution",
                category=GameKnowledgeCategory.STORAGE_AND_STATE,
                summary=(
                    "Managing versioned state schemas, calculating schema diffs, and executing "
                    "non-destructive migrations."
                ),
                key_invariants=(
                    "State schemas must carry an explicit version identifier (schema_version).",
                    "New fields added to schema must define deterministic default initializers.",
                    "Old match states loaded into newer engine versions must migrate losslessly.",
                ),
                anti_patterns=(
                    "Breaking match save compatibility on minor feature additions.",
                    "Unversioned raw state serialization.",
                ),
                recommended_patterns=(GameArchitecturePattern.PURE_CORE_HEADLESS,),
                testing_strategy=(
                    "Serialize v1 snapshot, run migration to v2, assert all v1 data preserved."
                ),
                tags=("schema", "migration", "state_evolution", "backward_compatibility", "save"),
            ),
            GameKnowledgeTopic(
                topic_id="backward_compatible_migration",
                name="Backward-Compatible Match Migration",
                category=GameKnowledgeCategory.STORAGE_AND_STATE,
                summary=(
                    "Non-destructive state upgrades supporting schema renames, defaults, "
                    "and deprecated field cleanup."
                ),
                key_invariants=(
                    "Migration steps must be pure functions with deterministic execution.",
                    "Missing fields in older snapshots receive target schema default values.",
                ),
                anti_patterns=(
                    "Dropping player progression or match history during state format upgrades.",
                ),
                recommended_patterns=(GameArchitecturePattern.PURE_CORE_HEADLESS,),
                testing_strategy=(
                    "Run regression suites on synthetic snapshots across all historical versions."
                ),
                tags=("migration", "backward_compatibility", "state", "versioning"),
            ),
            GameKnowledgeTopic(
                topic_id="feature_extension_invariants",
                name="Safe Feature Extension Invariants",
                category=GameKnowledgeCategory.ARCHITECTURE,
                summary=(
                    "Extending existing games by composing modular components without mutating "
                    "existing verified rule contracts."
                ),
                key_invariants=(
                    "New features must not alter behavior of existing passing unit tests.",
                    "New state properties must be composed through extension points.",
                    "Domain purity must be preserved across all newly generated files.",
                ),
                anti_patterns=("Rewriting working core systems when adding auxiliary features.",),
                recommended_patterns=(
                    GameArchitecturePattern.PURE_CORE_HEADLESS,
                    GameArchitecturePattern.MODEL_VIEW_PRESENTER,
                ),
                testing_strategy=(
                    "Execute full historical test suite alongside new feature tests."
                ),
                tags=("extension", "add_feature", "composition", "backward_compatibility"),
            ),
            GameKnowledgeTopic(
                topic_id="cognitive_debugging_and_repair",
                name="Cognitive Diagnosis & Root-Cause Isolation",
                category=GameKnowledgeCategory.TESTING_AND_REPAIR,
                summary=(
                    "Isolating non-trivial gameplay defects through telemetry analysis, "
                    "invariant checking, and hypothesis formulation."
                ),
                key_invariants=(
                    "Diagnosis consumes failure details, stack trace, and relevant domain rules.",
                    "Hypothesis must target the specific broken invariant.",
                    "Proposed patch modifies implementation only, never modifying tests.",
                ),
                anti_patterns=(
                    "Random code mutations without formulating a root-cause hypothesis.",
                    "Weakening test assertions to force a false passing result.",
                ),
                recommended_patterns=(GameArchitecturePattern.PURE_CORE_HEADLESS,),
                testing_strategy=(
                    "Verify repair results in 100% green tests without modifying test files."
                ),
                tags=("cognitive_repair", "diagnosis", "hypothesis", "root_cause", "telemetry"),
            ),
            GameKnowledgeTopic(
                topic_id="regression_safe_repair",
                name="Regression-Safe Specification Preservation",
                category=GameKnowledgeCategory.TESTING_AND_REPAIR,
                summary=(
                    "Repairing implementation while treating test specifications as "
                    "immutable sources of truth."
                ),
                key_invariants=(
                    "Test files must NEVER be modified, deleted, or weakened during repair.",
                    "All previously passing tests must remain passing after repair.",
                    "Repair iterations must be bounded to prevent infinite mutation loops.",
                ),
                anti_patterns=(
                    "Replacing failing assertions with pass or True.",
                    "Deleting failing unit tests to achieve green status.",
                ),
                recommended_patterns=(GameArchitecturePattern.PURE_CORE_HEADLESS,),
                testing_strategy=(
                    "Enforce strict audit: test_files_touched==False, tests_weakened==False."
                ),
                tags=("safety", "repair_safety", "specification_preservation", "regression"),
            ),
            GameKnowledgeTopic(
                topic_id="minimax_ai_decision",
                name="Deterministic Game AI & Evaluation",
                category=GameKnowledgeCategory.AI_AND_DECISION,
                summary=(
                    "AI opponents formulate decisions through heuristic board evaluation "
                    "and lookahead search."
                ),
                key_invariants=(
                    "AI evaluates pure GameState clones without modifying active match state.",
                    "Heuristic scoring weights safety, progression, and opponent captures.",
                    "AI operates through the exact same IGameIntent interface as human players.",
                ),
                anti_patterns=(
                    "AI cheating by inspecting private opponent hidden state or rigging RNG.",
                    "AI code executing blocking sleep loops on the main thread.",
                ),
                recommended_patterns=(
                    GameArchitecturePattern.PURE_CORE_HEADLESS,
                    GameArchitecturePattern.MODEL_VIEW_PRESENTER,
                ),
                testing_strategy=(
                    "Unit test AI move selection against known tactical board setups."
                ),
                tags=("ai", "minimax", "heuristics", "bot", "decision_making"),
            ),
            GameKnowledgeTopic(
                topic_id="test_driven_game_repair",
                name="Autonomous Diagnosis & Test-Driven Repair",
                category=GameKnowledgeCategory.TESTING_AND_REPAIR,
                summary=(
                    "Iterative closed-loop failure diagnosis and code mutation driven "
                    "by structured test telemetry."
                ),
                key_invariants=(
                    "Every bug report must reproduce as a failing headless unit test first.",
                    "Repair mutations must preserve architecture invariants and passing tests.",
                    "Repair cycles consume failure details (test name, assertion delta).",
                ),
                anti_patterns=(
                    "Blindly modifying unrelated code files when a test fails.",
                    "Suppressing test assertions to force a false green result.",
                ),
                recommended_patterns=(GameArchitecturePattern.PURE_CORE_HEADLESS,),
                testing_strategy=(
                    "Execute verification in sandbox; verify exit_code==0 and failed_count==0."
                ),
                tags=("repair", "testing", "diagnostics", "autonomous_loop", "tdd"),
            ),
        )


__all__ = ["GameKnowledgeCatalog"]
