"""End-to-end integration proof for the GameDev Capability.

Demonstrates the complete lifecycle:
Requirements -> Knowledge Retrieval -> Workflow Planning -> Component Composition
-> Pure GameCore Scaffolding -> Headless Verification -> Defect Injection ->
Autonomous Diagnosis & Repair -> Regression Invariant Preservation -> Final Green Verification.
"""

import tempfile
from collections.abc import Generator

import pytest

from app.domain.gamedev import (
    EngineTarget,
    GameArchitecturePattern,
    GameKnowledgeCategory,
    GameSystemType,
    GameWorkflowType,
)
from app.gamedev.agent import GameDevAgent
from app.gamedev.validator import GameArchitectureValidator
from app.tools.sandbox import CodeSandbox
from app.workspace.workspace import WorkspaceManager


@pytest.fixture
def temp_workspace() -> Generator[WorkspaceManager, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield WorkspaceManager(tmpdir)


@pytest.fixture
def sandbox() -> CodeSandbox:
    return CodeSandbox()


@pytest.mark.asyncio
async def test_complete_game_development_lifecycle_proof(
    temp_workspace: WorkspaceManager, sandbox: CodeSandbox
) -> None:
    """Proof of GameDev capability developing 'DiceTactics' deterministic pure-core game."""
    agent = GameDevAgent()

    # ──────────────────────────────────────────────────────────────────────────
    # Step 1 & 2: Requirements Analysis & Knowledge Retrieval
    # ──────────────────────────────────────────────────────────────────────────
    user_prompt = "Create a 2-player deterministic turn-based grid dice tactics game"

    # Query knowledge base
    knowledge_topics = agent.knowledge.search(
        "grid spatial indexing determinism turn fsm pure_core"
    )
    assert len(knowledge_topics) >= 3
    assert any(t.category == GameKnowledgeCategory.ARCHITECTURE for t in knowledge_topics)
    assert any(t.category == GameKnowledgeCategory.STATE_MANAGEMENT for t in knowledge_topics)
    assert any(t.category == GameKnowledgeCategory.GAMEPLAY_SYSTEMS for t in knowledge_topics)

    # ──────────────────────────────────────────────────────────────────────────
    # Step 3: Workflow Planning
    # ──────────────────────────────────────────────────────────────────────────
    workflow_plan = agent.plan_workflow(
        workflow_type=GameWorkflowType.CREATE_GAME,
        goal=user_prompt,
        target=EngineTarget.PURE_CORE,
    )
    assert workflow_plan.workflow_type == GameWorkflowType.CREATE_GAME
    assert len(workflow_plan.steps) == 5
    assert GameArchitecturePattern.PURE_CORE_HEADLESS in workflow_plan.applied_patterns
    assert any(
        c.system_type == GameSystemType.TURN_MANAGER for c in workflow_plan.required_components
    )
    assert any(c.system_type == GameSystemType.DICE_RNG for c in workflow_plan.required_components)
    assert any(
        c.system_type == GameSystemType.GRID_BOARD for c in workflow_plan.required_components
    )

    # ──────────────────────────────────────────────────────────────────────────
    # Step 4: Pure GameCore Implementation (DiceTactics)
    # ──────────────────────────────────────────────────────────────────────────
    project_dir = "dice_tactics"

    # 1. Domain contracts
    contracts_py = """from enum import Enum
from dataclasses import dataclass

class GamePhase(str, Enum):
    NOT_STARTED = "not_started"
    TURN_ACTIVE = "turn_active"
    DICE_ROLLED = "dice_rolled"
    TOKEN_MOVED = "token_moved"
    GAME_OVER = "game_over"

@dataclass(frozen=True, slots=True)
class MoveIntent:
    player_id: int
    target_x: int
    target_y: int

@dataclass(frozen=True, slots=True)
class RollIntent:
    player_id: int
"""
    temp_workspace.write(f"{project_dir}/domain/contracts.py", contracts_py)

    # 2. Grid system
    grid_py = """from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class GridBoard:
    width: int = 8
    height: int = 8

    def is_in_bounds(self, x: int, y: int) -> bool:
        if x < 0 or x >= self.width:
            return False
        if y < 0 or y >= self.height:
            return False
        return True

    def manhattan_distance(self, x1: int, y1: int, x2: int, y2: int) -> int:
        return abs(x1 - x2) + abs(y1 - y2)
"""
    temp_workspace.write(f"{project_dir}/systems/grid.py", grid_py)

    # 3. Dice system
    dice_py = """import random

class DiceRng:
    def __init__(self, seed: int = 42) -> None:
        self._rng = random.Random(seed)

    def roll(self, sides: int = 6) -> int:
        if sides < 1:
            raise ValueError("Sides must be at least 1")
        return self._rng.randint(1, sides)
"""
    temp_workspace.write(f"{project_dir}/systems/dice.py", dice_py)

    # 4. Turn manager
    turn_py = """class TurnManager:
    def __init__(self, player_count: int = 2) -> None:
        self.player_count = player_count
        self.active_player = 0
        self.turn_number = 1

    def next_turn(self) -> None:
        self.active_player = (self.active_player + 1) % self.player_count
        if self.active_player == 0:
            self.turn_number += 1
"""
    temp_workspace.write(f"{project_dir}/systems/turn.py", turn_py)

    # 5. Authoritative Rules Engine
    rules_py = """from domain.contracts import GamePhase, MoveIntent, RollIntent
from systems.grid import GridBoard
from systems.dice import DiceRng
from systems.turn import TurnManager

class DiceTacticsGame:
    def __init__(self, seed: int = 1337) -> None:
        self.grid = GridBoard(width=8, height=8)
        self.dice = DiceRng(seed=seed)
        self.turns = TurnManager(player_count=2)
        self.phase = GamePhase.TURN_ACTIVE
        self.positions = {0: (0, 0), 1: (7, 7)}
        self.goals = {0: (7, 7), 1: (0, 0)}
        self.last_roll = 0
        self.winner = None

    def roll_dice(self, intent: RollIntent) -> int:
        if self.phase != GamePhase.TURN_ACTIVE:
            raise ValueError(f"Cannot roll in phase {self.phase}")
        if intent.player_id != self.turns.active_player:
            raise ValueError(f"Not player {intent.player_id}'s turn")

        self.last_roll = self.dice.roll(sides=6)
        self.phase = GamePhase.DICE_ROLLED
        return self.last_roll

    def move_token(self, intent: MoveIntent) -> bool:
        if self.phase != GamePhase.DICE_ROLLED:
            raise ValueError(f"Must roll dice before moving, current phase: {self.phase}")
        if intent.player_id != self.turns.active_player:
            raise ValueError("Not your turn")

        cur_x, cur_y = self.positions[intent.player_id]
        if not self.grid.is_in_bounds(intent.target_x, intent.target_y):
            return False

        dist = self.grid.manhattan_distance(cur_x, cur_y, intent.target_x, intent.target_y)
        if dist != self.last_roll:
            return False

        self.positions[intent.player_id] = (intent.target_x, intent.target_y)

        # Check win
        if (intent.target_x, intent.target_y) == self.goals[intent.player_id]:
            self.phase = GamePhase.GAME_OVER
            self.winner = intent.player_id
            return True

        # Advance turn
        self.turns.next_turn()
        self.phase = GamePhase.TURN_ACTIVE
        return True
"""
    temp_workspace.write(f"{project_dir}/systems/rules.py", rules_py)

    # 6. Comprehensive Unit Tests
    test_py = """import pytest
from domain.contracts import GamePhase, MoveIntent, RollIntent
from systems.rules import DiceTacticsGame

def test_initial_state():
    game = DiceTacticsGame(seed=42)
    assert game.phase == GamePhase.TURN_ACTIVE
    assert game.turns.active_player == 0
    assert game.turns.turn_number == 1
    assert game.positions[0] == (0, 0)
    assert game.positions[1] == (7, 7)
    assert game.winner is None

def test_roll_dice_phase_transition():
    game = DiceTacticsGame(seed=42)
    roll = game.roll_dice(RollIntent(player_id=0))
    assert 1 <= roll <= 6
    assert game.phase == GamePhase.DICE_ROLLED
    assert game.last_roll == roll

def test_illegal_turn_intent_rejected():
    game = DiceTacticsGame(seed=42)
    with pytest.raises(ValueError, match="Not player 1's turn"):
        game.roll_dice(RollIntent(player_id=1))

def test_move_without_roll_rejected():
    game = DiceTacticsGame(seed=42)
    with pytest.raises(ValueError, match="Must roll dice before moving"):
        game.move_token(MoveIntent(player_id=0, target_x=1, target_y=0))

def test_out_of_bounds_move_rejected():
    game = DiceTacticsGame(seed=42)
    game.roll_dice(RollIntent(player_id=0))
    # Deliberate out of bounds move
    res = game.move_token(MoveIntent(player_id=0, target_x=-1, target_y=0))
    assert res is False
    assert game.positions[0] == (0, 0)

def test_valid_move_advances_turn():
    game = DiceTacticsGame(seed=42)
    roll = game.roll_dice(RollIntent(player_id=0))
    # Move horizontally by exact roll value
    res = game.move_token(MoveIntent(player_id=0, target_x=roll, target_y=0))
    assert res is True
    assert game.positions[0] == (roll, 0)
    assert game.turns.active_player == 1
    assert game.phase == GamePhase.TURN_ACTIVE

def test_boundary_check_max_bounds():
    from systems.grid import GridBoard
    grid = GridBoard(width=8, height=8)
    assert grid.is_in_bounds(0, 0) is True
    assert grid.is_in_bounds(7, 7) is True
    assert grid.is_in_bounds(8, 7) is False
    assert grid.is_in_bounds(7, 8) is False
"""
    temp_workspace.write(f"{project_dir}/tests/test_game.py", test_py)

    # ──────────────────────────────────────────────────────────────────────────
    # Step 5: Static Architecture Validation
    # ──────────────────────────────────────────────────────────────────────────
    validation_report = GameArchitectureValidator.validate_workspace(temp_workspace, project_dir)
    assert validation_report.is_valid
    assert validation_report.error_count == 0

    # ──────────────────────────────────────────────────────────────────────────
    # Step 6: Headless Verification in Sandbox
    # ──────────────────────────────────────────────────────────────────────────
    initial_verify = await agent.verify_game(temp_workspace, project_dir, sandbox)
    assert initial_verify.success
    assert initial_verify.exit_code == 0
    assert initial_verify.passed_count == 7
    assert initial_verify.failed_count == 0

    # ──────────────────────────────────────────────────────────────────────────
    # Step 7: Intentional Defect Injection
    # ──────────────────────────────────────────────────────────────────────────
    # Introduce an off-by-one bug in systems/grid.py (x > self.width instead of x >= self.width)
    defective_grid = grid_py.replace("x >= self.width", "x > self.width")
    temp_workspace.write(f"{project_dir}/systems/grid.py", defective_grid)

    # Re-verify: must fail on test_boundary_check_max_bounds
    failing_verify = await agent.verify_game(temp_workspace, project_dir, sandbox)
    assert not failing_verify.success
    assert failing_verify.failed_count >= 1
    assert "test_boundary_check_max_bounds" in failing_verify.failed_tests

    # ──────────────────────────────────────────────────────────────────────────
    # Step 8: Autonomous Diagnosis & Repair
    # ──────────────────────────────────────────────────────────────────────────
    repaired_report = await agent.diagnose_and_repair(
        temp_workspace,
        project_dir,
        sandbox,
        max_iterations=3,
    )

    # Must converge to green
    assert repaired_report.success
    assert repaired_report.exit_code == 0
    assert repaired_report.failed_count == 0
    assert repaired_report.metadata.get("repaired") is True

    # ──────────────────────────────────────────────────────────────────────────
    # Step 9: Invariant Preservation Verification
    # ──────────────────────────────────────────────────────────────────────────
    # 1. Assert grid.py was corrected to x >= self.width
    repaired_grid_code = temp_workspace.read(f"{project_dir}/systems/grid.py")["content"]
    assert "x >= self.width" in repaired_grid_code

    # 2. Assert test file assertions were preserved without weakening
    test_code_after_repair = temp_workspace.read(f"{project_dir}/tests/test_game.py")["content"]
    assert "assert grid.is_in_bounds(8, 7) is False" in test_code_after_repair
    assert "assert 1 <= roll <= 6" in test_code_after_repair

    # 3. Assert zero engine imports were added (domain purity preserved)
    final_validation = GameArchitectureValidator.validate_workspace(temp_workspace, project_dir)
    assert final_validation.is_valid
    assert final_validation.error_count == 0
