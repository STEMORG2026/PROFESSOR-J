"""Game Development Workflow Engine — Goal-driven operational lifecycles.

Coordinates structured, repeatable workflows:
- CREATE_GAME
- ADD_FEATURE
- FIX_BUG
- REFACTOR_SYSTEM
- TEST_AND_REPAIR
- OPTIMIZE
"""

from __future__ import annotations

import logging
from typing import Any

from app.domain.gamedev import (
    EngineTarget,
    GameArchitecturePattern,
    GameComponentSpec,
    GameWorkflowPlan,
    GameWorkflowType,
)
from app.gamedev.components import GameComponentCatalog
from app.gamedev.knowledge import GameKnowledgeCatalog

logger = logging.getLogger(__name__)


class GameWorkflowEngine:
    """Orchestrator for game development operational workflows."""

    def __init__(
        self,
        knowledge_catalog: GameKnowledgeCatalog | None = None,
        component_catalog: GameComponentCatalog | None = None,
    ) -> None:
        self.knowledge = knowledge_catalog or GameKnowledgeCatalog()
        self.components = component_catalog or GameComponentCatalog()

    def plan_workflow(
        self,
        workflow_type: GameWorkflowType,
        goal: str,
        target_project: str = "",
        target_engine: EngineTarget = EngineTarget.PURE_CORE,
        metadata: dict[str, Any] | None = None,
    ) -> GameWorkflowPlan:
        """Formulate a structured workflow plan with rich metadata for the given goal."""
        low = goal.lower()
        required_comps: list[GameComponentSpec] = []
        applied_patterns: list[GameArchitecturePattern] = [
            GameArchitecturePattern.PURE_CORE_HEADLESS
        ]
        affected_systems: list[str] = []
        affected_state: list[str] = []
        extension_points: list[str] = []
        required_knowledge: list[str] = []
        expected_invariants: list[str] = []
        tests_to_add: list[str] = []
        migration_required = False
        verification_strategy = (
            "Run isolated unit test suite in CodeSandbox; assert zero regressions."
        )

        # 1. Deduce components, systems, and knowledge
        if "inventory" in low or "item" in low or "equipment" in low:
            required_comps.append(self.components.inventory())
            affected_systems.append("InventoryManager")
            affected_state.append("player_inventories")
            extension_points.append("GameState.inventories")
            required_knowledge.append("inventory_invariants")
            required_knowledge.append("state_schema_evolution")
            expected_invariants.append(
                "Inventory capacity cannot exceed maximum configured slot limit."
            )
            expected_invariants.append("Item quantities must be strictly positive integers.")
            tests_to_add.append("test_add_item_within_capacity")
            tests_to_add.append("test_item_stacking_limits")
            tests_to_add.append("test_remove_item_success_and_underflow")
            migration_required = True

        if "score" in low or "leaderboard" in low:
            required_comps.append(self.components.score_manager())
            affected_systems.append("ScoreManager")
            affected_state.append("player_scores")
            extension_points.append("GameState.scores")
            migration_required = True

        if "ai" in low or "bot" in low or "minimax" in low:
            required_comps.append(self.components.ai_minimax())
            affected_systems.append("MinimaxAI")
            required_knowledge.append("minimax_ai_decision")

        if "turn" in low or "board" in low or "strategy" in low or "ludo" in low:
            required_comps.append(self.components.turn_manager())
            applied_patterns.append(GameArchitecturePattern.STATE_MACHINE_EVENT_DRIVEN)
            required_knowledge.append("state_machine_fsm")

        if "dice" in low or "roll" in low or "random" in low or "ludo" in low:
            required_comps.append(self.components.dice_rng())
            required_knowledge.append("game_loop_determinism")

        if "grid" in low or "tile" in low:
            required_comps.append(self.components.grid_board())
            required_knowledge.append("grid_spatial_indexing")

        if not required_comps:
            required_comps.append(self.components.event_bus())

        # 2. Step synthesis based on workflow type
        steps: tuple[str, ...]
        if workflow_type == GameWorkflowType.CREATE_GAME:
            steps = (
                f"1. Formulate domain requirements and invariants for: '{goal}'",
                "2. Query GameKnowledgeCatalog for architectural patterns.",
                f"3. Scaffold pure domain architecture with {len(required_comps)} components.",
                "4. Run GameArchitectureValidator to ensure domain purity.",
                "5. Execute headless verification in CodeSandbox to establish green baseline.",
            )
        elif workflow_type == GameWorkflowType.ADD_FEATURE:
            steps = (
                f"1. Inspect existing project '{target_project}' architecture and state model.",
                f"2. Formulate StateSchemaDiff for new state fields: {affected_state}.",
                "3. Synthesize component implementation & wire into GameState.",
                f"4. Generate unit tests covering: {tests_to_add}.",
                "5. Execute headless verification in sandbox to verify zero regressions.",
            )
        elif workflow_type == GameWorkflowType.FIX_BUG:
            steps = (
                f"1. Formulate a reproducing unit test for symptom: '{goal}'",
                "2. Execute headless verification to capture failure diagnostics.",
                "3. Query GameKnowledgeCatalog for repair patterns and state invariants.",
                "4. Apply targeted code mutation to correct domain rule logic.",
                "5. Re-run headless verification to confirm resolution and zero regressions.",
            )
        elif workflow_type == GameWorkflowType.TEST_AND_REPAIR:
            steps = (
                "1. Execute headless test verification in CodeSandbox.",
                "2. Inspect GameTestReport failure_details and isolate failing assertions.",
                "3. Perform closed-loop code mutation and test execution cycles until green.",
                "4. Produce final structured verification report.",
            )
        elif workflow_type == GameWorkflowType.REFACTOR_SYSTEM:
            steps = (
                f"1. Identify refactoring target and invariants to preserve for: '{goal}'",
                "2. Restructure domain components and interfaces cleanly.",
                "3. Run static architecture validator.",
                "4. Execute headless test suite to prove behavioral equivalence.",
            )
        else:  # OPTIMIZE
            steps = (
                f"1. Profile memory allocation and execution bottlenecks for: '{goal}'",
                "2. Optimize algorithmic complexity and data structures.",
                "3. Re-verify behavioral equivalence with headless test suite.",
            )

        seen_comp_names: set[str] = set()
        deduped_comps: list[GameComponentSpec] = []
        for c in required_comps:
            if c.name not in seen_comp_names:
                seen_comp_names.add(c.name)
                deduped_comps.append(c)

        return GameWorkflowPlan(
            workflow_type=workflow_type,
            goal=goal,
            steps=steps,
            target_project=target_project,
            requested_feature=goal if workflow_type == GameWorkflowType.ADD_FEATURE else "",
            affected_systems=tuple(dict.fromkeys(affected_systems)),
            affected_state=tuple(dict.fromkeys(affected_state)),
            extension_points=tuple(dict.fromkeys(extension_points)),
            required_components=tuple(deduped_comps),
            required_knowledge=tuple(dict.fromkeys(required_knowledge)),
            expected_invariants=tuple(dict.fromkeys(expected_invariants)),
            tests_to_add=tuple(dict.fromkeys(tests_to_add)),
            migration_required=migration_required,
            verification_strategy=verification_strategy,
            applied_patterns=tuple(dict.fromkeys(applied_patterns)),
            target_engine=target_engine,
            metadata=metadata or {},
        )


__all__ = ["GameWorkflowEngine"]
