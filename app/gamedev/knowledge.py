"""Game Development Knowledge Base — Structured, queryable engineering knowledge.

Provides the GameDevAgent with structured architectural rules, patterns, anti-patterns,
and testing strategies across game engineering domains.
"""

from __future__ import annotations

import logging
import re

from app.domain.gamedev import (
    GameArchitecturePattern,
    GameKnowledgeCategory,
    GameKnowledgeTopic,
)

logger = logging.getLogger(__name__)


class GameKnowledgeCatalog:
    """Registry and query engine for structured game development knowledge."""

    def __init__(self, topics: tuple[GameKnowledgeTopic, ...] | None = None) -> None:
        self._topics: dict[str, GameKnowledgeTopic] = {}
        initial_topics = topics or self._default_topics()
        for t in initial_topics:
            self.register(t)

    def register(self, topic: GameKnowledgeTopic) -> None:
        """Register a knowledge topic."""
        self._topics[topic.topic_id] = topic

    def get(self, topic_id: str) -> GameKnowledgeTopic | None:
        """Retrieve topic by ID."""
        return self._topics.get(topic_id)

    def get_by_category(self, category: GameKnowledgeCategory) -> list[GameKnowledgeTopic]:
        """List all topics within a category."""
        return [t for t in self._topics.values() if t.category == category]

    def all_topics(self) -> list[GameKnowledgeTopic]:
        """List all registered knowledge topics."""
        return list(self._topics.values())

    def search(self, query: str) -> list[GameKnowledgeTopic]:
        """Semantic/keyword search across topics, tags, invariants, and summaries."""
        terms = [t.lower() for t in re.split(r"\W+", query) if len(t) > 2]
        if not terms:
            return list(self._topics.values())

        scored: list[tuple[int, GameKnowledgeTopic]] = []
        for topic in self._topics.values():
            score = 0
            text_corpus = (
                f"{topic.topic_id} {topic.name} {topic.category.value} {topic.summary} "
                f"{' '.join(topic.tags)} {' '.join(topic.key_invariants)} "
                f"{' '.join(topic.anti_patterns)}"
            ).lower()

            for term in terms:
                if term in topic.tags:
                    score += 5
                if term in topic.topic_id.lower():
                    score += 4
                if term in topic.name.lower():
                    score += 3
                if term in text_corpus:
                    score += 1

            if score > 0:
                scored.append((score, topic))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored]

    @staticmethod
    def _default_topics() -> tuple[GameKnowledgeTopic, ...]:
        """Built-in structured game engineering knowledge topics."""
        return (
            GameKnowledgeTopic(
                topic_id="pure_core_presentation_separation",
                name="Pure Core / Presentation Separation",
                category=GameKnowledgeCategory.ARCHITECTURE,
                summary=(
                    "Game rules must execute as pure, headless, deterministic state machines "
                    "with ZERO engine coupling."
                ),
                key_invariants=(
                    "Authoritative game rules live in pure domain assemblies (e.g. GameCore).",
                    "Pure rules have zero imports from UnityEngine, Godot, or Unreal runtimes.",
                    "Presentation layers only observe domain state and dispatch player intents.",
                    "Game logic is 100% testable headlessly without launching an engine editor.",
                ),
                anti_patterns=(
                    "Writing win/loss conditions inside UI or MonoBehaviour update loops.",
                    "Using UnityEngine.Random or time-dependent physics for authoritative state.",
                    "Allowing domain rules to import UI canvas or audio player classes.",
                ),
                recommended_patterns=(
                    GameArchitecturePattern.PURE_CORE_HEADLESS,
                    GameArchitecturePattern.MODEL_VIEW_PRESENTER,
                ),
                testing_strategy=(
                    "Unit test game state transitions with deterministic seed inputs; "
                    "assert zero engine runtime imports."
                ),
                tags=("architecture", "pure_core", "headless", "clean_code", "invariants"),
            ),
            GameKnowledgeTopic(
                topic_id="game_loop_determinism",
                name="Deterministic Game Loops & State Steps",
                category=GameKnowledgeCategory.STATE_MANAGEMENT,
                summary=(
                    "Game state progresses via discrete, reproducible simulation ticks "
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
