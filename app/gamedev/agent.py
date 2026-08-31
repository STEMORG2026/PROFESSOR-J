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
    GameProjectModel,
    GameProjectSpec,
    GameRepairAudit,
    GameTestReport,
    GameValidationReport,
    GameWorkflowPlan,
    GameWorkflowType,
    StateMigrationResult,
    StateSchemaDiff,
)
from app.exceptions import SandboxTimeoutError
from app.gamedev.adapters.pure_core import PureCoreAdapter
from app.gamedev.analyzer import GameProjectAnalyzer
from app.gamedev.base import EngineRegistry
from app.gamedev.components import GameComponentCatalog
from app.gamedev.knowledge import GameKnowledgeCatalog
from app.gamedev.repair import CognitiveRepairEngine
from app.gamedev.schema import GameStateEvolutionEngine, GameStateSchema
from app.gamedev.workflows import GameWorkflowEngine
from app.tools.sandbox import CodeSandbox
from app.workspace.workspace import WorkspaceManager

logger = logging.getLogger(__name__)


class GameDevAgent:
    """Specialized agent for game development capabilities."""

    def __init__(
        self,
        registry: EngineRegistry | None = None,
        knowledge: GameKnowledgeCatalog | None = None,
        workflow_engine: GameWorkflowEngine | None = None,
        repair_engine: CognitiveRepairEngine | None = None,
        schema_engine: GameStateEvolutionEngine | None = None,
        analyzer: GameProjectAnalyzer | None = None,
    ) -> None:
        self.registry = registry or self._default_registry()
        self.knowledge = knowledge or GameKnowledgeCatalog()
        self.workflow_engine = workflow_engine or GameWorkflowEngine(
            knowledge_catalog=self.knowledge
        )
        self.repair_engine = repair_engine or CognitiveRepairEngine(
            knowledge_catalog=self.knowledge
        )
        self.schema_engine = schema_engine or GameStateEvolutionEngine()
        self.analyzer = analyzer or GameProjectAnalyzer()

    def analyze_project(
        self,
        workspace: WorkspaceManager,
        project_dir: str = "",
    ) -> GameProjectModel:
        """Inspect and build a structural representation of a game project."""
        return self.analyzer.analyze_project(workspace, project_dir)

    @staticmethod
    def _default_registry() -> EngineRegistry:
        reg = EngineRegistry()
        reg.register(PureCoreAdapter())
        return reg

    def plan_workflow(
        self,
        workflow_type: GameWorkflowType,
        goal: str,
        target_project: str = "",
        target: EngineTarget = EngineTarget.PURE_CORE,
    ) -> GameWorkflowPlan:
        """Formulate a goal-driven operational workflow plan with structured metadata."""
        return self.workflow_engine.plan_workflow(
            workflow_type=workflow_type,
            goal=goal,
            target_project=target_project,
            target_engine=target,
        )

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

    async def verify_game(
        self,
        workspace: WorkspaceManager,
        project_dir: str,
        sandbox: CodeSandbox,
        target: EngineTarget = EngineTarget.PURE_CORE,
    ) -> GameTestReport:
        """Execute headless verification in the isolated sandbox."""
        resolved_path = workspace._resolve(project_dir)
        if not resolved_path.exists() or not resolved_path.is_dir():
            return GameTestReport(
                success=False,
                exit_code=1,
                passed_count=0,
                failed_count=1,
                duration_ms=0.0,
                error=f"Project directory '{project_dir}' does not exist inside workspace.",
            )

        adapter = self.registry.get(target) or self.registry.require(EngineTarget.PURE_CORE)
        test_cmd = adapter.get_test_command(str(resolved_path))

        try:
            sandbox_result = await sandbox.run_command(test_cmd, cwd=resolved_path)
            return adapter.parse_test_output(sandbox_result)
        except SandboxTimeoutError as exc:
            timeout_val = exc.context.get("timeout", 10)
            return GameTestReport(
                success=False,
                exit_code=124,
                passed_count=0,
                failed_count=1,
                duration_ms=float(timeout_val * 1000),
                error=f"Test execution timed out after {timeout_val}s.",
                timed_out=True,
            )
        except Exception as exc:
            return GameTestReport(
                success=False,
                exit_code=1,
                passed_count=0,
                failed_count=1,
                duration_ms=0.0,
                error=str(exc),
            )

    async def diagnose_and_repair(
        self,
        workspace: WorkspaceManager,
        project_dir: str,
        sandbox: CodeSandbox,
        target: EngineTarget = EngineTarget.PURE_CORE,
        max_iterations: int = 3,
    ) -> GameTestReport:
        """Autonomous iterative test, cognitive diagnose, and regression-safe repair loop."""
        initial_report = await self.verify_game(workspace, project_dir, sandbox, target=target)
        if initial_report.success or max_iterations <= 1:
            return initial_report

        current_report = initial_report
        last_audit: GameRepairAudit | None = None

        for iteration in range(1, max_iterations + 1):
            if current_report.success:
                return GameTestReport(
                    success=True,
                    exit_code=0,
                    passed_count=current_report.passed_count,
                    failed_count=0,
                    duration_ms=current_report.duration_ms,
                    stdout=current_report.stdout,
                    stderr=current_report.stderr,
                    failed_tests=(),
                    failure_details=(),
                    repair_audit=last_audit,
                    metadata={
                        "repaired": True,
                        "iterations": iteration - 1,
                        "initial_failures": initial_report.failed_tests,
                    },
                )

            repaired, audit = self.repair_engine.attempt_cognitive_repair(
                workspace, project_dir, current_report, iteration=iteration
            )
            last_audit = audit
            if not repaired:
                break

            current_report = await self.verify_game(workspace, project_dir, sandbox, target=target)

        return GameTestReport(
            success=current_report.success,
            exit_code=current_report.exit_code,
            passed_count=current_report.passed_count,
            failed_count=current_report.failed_count,
            duration_ms=current_report.duration_ms,
            stdout=current_report.stdout,
            stderr=current_report.stderr,
            error=current_report.error,
            timed_out=current_report.timed_out,
            failed_tests=current_report.failed_tests,
            failure_details=current_report.failure_details,
            repair_audit=last_audit,
            metadata={
                "repaired": current_report.success,
                "iterations": max_iterations,
                "initial_failures": initial_report.failed_tests,
            },
        )

    def evolve_state_schema(
        self,
        old_schema: GameStateSchema,
        new_schema: GameStateSchema,
        renames: dict[str, str] | None = None,
    ) -> StateSchemaDiff:
        """Compute structural schema diff between two state versions."""
        return self.schema_engine.compute_diff(old_schema, new_schema, renames)

    def migrate_state_snapshot(
        self,
        state_dict: dict[str, Any],
        diff: StateSchemaDiff,
    ) -> StateMigrationResult:
        """Migrate a raw state snapshot according to a schema diff."""
        return self.schema_engine.migrate_state(state_dict, diff)


__all__ = ["GameDevAgent"]
