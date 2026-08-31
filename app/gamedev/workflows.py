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
        target_engine: EngineTarget = EngineTarget.PURE_CORE,
        metadata: dict[str, Any] | None = None,
    ) -> GameWorkflowPlan:
        """Formulate a structured workflow plan for the given goal."""
        low = goal.lower()
        required_comps: list[GameComponentSpec] = []
        applied_patterns: list[GameArchitecturePattern] = [
            GameArchitecturePattern.PURE_CORE_HEADLESS
        ]

        # Knowledge-driven component & pattern deduction
        if "turn" in low or "board" in low or "strategy" in low or "ludo" in low:
            required_comps.append(self.components.turn_manager())
            applied_patterns.append(GameArchitecturePattern.STATE_MACHINE_EVENT_DRIVEN)

        if "dice" in low or "roll" in low or "random" in low or "ludo" in low:
            required_comps.append(self.components.dice_rng())

        if "board" in low or "grid" in low or "tile" in low or "ludo" in low:
            required_comps.append(self.components.grid_board())

        if "event" in low or "bus" in low or "listener" in low or not required_comps:
            required_comps.append(self.components.event_bus())

        # Step synthesis based on workflow type
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
                f"1. Analyze existing project structure for extension points: '{goal}'",
                "2. Synthesize new domain contracts, state properties, and intent handlers.",
                "3. Generate pure component implementation and register with GameState.",
                "4. Synthesize unit tests covering new feature behavior.",
                "5. Execute headless verification to ensure zero regressions.",
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

        return GameWorkflowPlan(
            workflow_type=workflow_type,
            goal=goal,
            steps=steps,
            required_components=tuple(required_comps),
            applied_patterns=tuple(dict.fromkeys(applied_patterns)),
            target_engine=target_engine,
            metadata=metadata or {},
        )


__all__ = ["GameWorkflowEngine"]
