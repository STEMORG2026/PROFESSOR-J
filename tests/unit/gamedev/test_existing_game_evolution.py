"""Comprehensive verification of Existing-Game Development, State Migration & Cognitive Repair.

Tests the full v0.2 milestone:
CREATE -> UNDERSTAND -> EXTEND (ADD_FEATURE) -> STATE MIGRATION -> BREAK ->
DIAGNOSE -> COGNITIVE REPAIR -> REPAIR SAFETY -> REGRESSION VERIFICATION -> SECOND CONSUMER PROOF.
"""

import tempfile
from collections.abc import Generator

import pytest

from app.domain.gamedev import (
    GameSystemType,
    GameWorkflowType,
)
from app.gamedev.agent import GameDevAgent
from app.gamedev.schema import GameStateEvolutionEngine, GameStateSchema
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


def _scaffold_base_dice_tactics(
    workspace: WorkspaceManager, project_dir: str = "dice_tactics"
) -> None:
    """Helper to scaffold the baseline DiceTactics pure GameCore."""
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
    workspace.write(f"{project_dir}/domain/contracts.py", contracts_py)

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
    workspace.write(f"{project_dir}/systems/grid.py", grid_py)

    dice_py = """import random

class DiceRng:
    def __init__(self, seed: int = 42) -> None:
        self._rng = random.Random(seed)

    def roll(self, sides: int = 6) -> int:
        if sides < 1:
            raise ValueError("Sides must be at least 1")
        return self._rng.randint(1, sides)
"""
    workspace.write(f"{project_dir}/systems/dice.py", dice_py)

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
    workspace.write(f"{project_dir}/systems/turn.py", turn_py)

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

        if (intent.target_x, intent.target_y) == self.goals[intent.player_id]:
            self.phase = GamePhase.GAME_OVER
            self.winner = intent.player_id
            return True

        self.turns.next_turn()
        self.phase = GamePhase.TURN_ACTIVE
        return True
"""
    workspace.write(f"{project_dir}/systems/rules.py", rules_py)

    test_py = """import pytest
from domain.contracts import GamePhase, MoveIntent, RollIntent
from systems.rules import DiceTacticsGame

def test_initial_state():
    game = DiceTacticsGame(seed=42)
    assert game.phase == GamePhase.TURN_ACTIVE
    assert game.turns.active_player == 0

def test_valid_move_cycle():
    game = DiceTacticsGame(seed=42)
    roll = game.roll_dice(RollIntent(player_id=0))
    res = game.move_token(MoveIntent(player_id=0, target_x=roll, target_y=0))
    assert res is True
    assert game.turns.active_player == 1
"""
    workspace.write(f"{project_dir}/tests/test_game.py", test_py)


def test_generic_state_schema_evolution_and_migration() -> None:
    """1. Generic State Schema Evolution handles additions, renames, and migrations."""
    schema_v1 = GameStateSchema(
        version=1,
        fields={
            "positions": {"type": "dict", "default": {}},
            "active_player": {"type": "int", "default": 0},
            "old_score_field": {"type": "int", "default": 0},
        },
    )

    schema_v2 = GameStateSchema(
        version=2,
        fields={
            "positions": {"type": "dict", "default": {}},
            "active_player": {"type": "int", "default": 0},
            "player_scores": {"type": "dict", "default": lambda: {0: 0, 1: 0}},
            "inventories": {"type": "dict", "default": lambda: {0: [], 1: []}},
        },
    )

    engine = GameStateEvolutionEngine()
    diff = engine.compute_diff(schema_v1, schema_v2, renames={"old_score_field": "player_scores"})

    assert diff.from_version == 1
    assert diff.to_version == 2
    assert diff.requires_migration is True
    assert any(a.field_name == "inventories" for a in diff.added_fields)
    assert any(r.field_name == "player_scores" for r in diff.renamed_fields)

    # Migrate a v1 match snapshot
    v1_snapshot = {
        "schema_version": 1,
        "positions": {0: (0, 0), 1: (7, 7)},
        "active_player": 0,
        "old_score_field": 100,
    }

    migration_result = engine.migrate_state(v1_snapshot, diff)
    assert migration_result.success is True
    assert migration_result.to_version == 2
    assert migration_result.migrated_state["schema_version"] == 2
    assert migration_result.migrated_state["player_scores"] == 100
    assert "old_score_field" not in migration_result.migrated_state
    assert 0 in migration_result.migrated_state["inventories"]


@pytest.mark.asyncio
async def test_add_feature_inventory_extension_and_cognitive_repair(
    temp_workspace: WorkspaceManager, sandbox: CodeSandbox
) -> None:
    """2. Full ADD_FEATURE workflow with cognitive defect repair on DiceTactics."""
    agent = GameDevAgent()
    project_dir = "dice_tactics"

    # Step 1: Scaffold baseline game
    _scaffold_base_dice_tactics(temp_workspace, project_dir)
    baseline_report = await agent.verify_game(temp_workspace, project_dir, sandbox)
    assert baseline_report.success
    assert baseline_report.passed_count == 2

    # Step 2: Plan ADD_FEATURE workflow with structured metadata
    plan = agent.plan_workflow(
        workflow_type=GameWorkflowType.ADD_FEATURE,
        goal="Add an inventory/equipment system to this existing game",
        target_project=project_dir,
    )
    assert plan.workflow_type == GameWorkflowType.ADD_FEATURE
    assert plan.migration_required is True
    assert "InventoryManager" in plan.affected_systems
    assert "player_inventories" in plan.affected_state
    assert "inventory_invariants" in plan.required_knowledge
    assert any(c.system_type == GameSystemType.INVENTORY for c in plan.required_components)

    # Step 3: Implement generic inventory subsystem in project
    inventory_py = """from dataclasses import dataclass, field

@dataclass
class InventoryItem:
    item_id: str
    quantity: int = 1
    max_stack: int = 99

class InventoryManager:
    def __init__(self, max_capacity: int = 5) -> None:
        self.max_capacity = max_capacity
        self.items: dict[str, int] = {}

    def add_item(self, item_id: str, quantity: int = 1) -> bool:
        if quantity <= 0:
            return False
        if item_id not in self.items and len(self.items) >= self.max_capacity:
            return False
        self.items[item_id] = self.items.get(item_id, 0) + quantity
        return True

    def remove_item(self, item_id: str, quantity: int = 1) -> bool:
        if quantity <= 0 or item_id not in self.items:
            return False
        if self.items[item_id] < quantity:
            return False
        self.items[item_id] -= quantity
        if self.items[item_id] == 0:
            del self.items[item_id]
        return True

    def get_count(self, item_id: str) -> int:
        return self.items.get(item_id, 0)
"""
    temp_workspace.write(f"{project_dir}/systems/inventory.py", inventory_py)

    # Step 4: Add inventory unit tests (Specification)
    inv_test_py = """import pytest
from systems.inventory import InventoryManager

def test_inventory_add_and_remove():
    inv = InventoryManager(max_capacity=3)
    assert inv.add_item("speed_boots", 1) is True
    assert inv.get_count("speed_boots") == 1
    assert inv.remove_item("speed_boots", 1) is True
    assert inv.get_count("speed_boots") == 0

def test_inventory_capacity_limit():
    inv = InventoryManager(max_capacity=2)
    assert inv.add_item("item_1", 1) is True
    assert inv.add_item("item_2", 1) is True
    # Third distinct item must exceed capacity
    assert inv.add_item("item_3", 1) is False

def test_inventory_invalid_quantity():
    inv = InventoryManager(max_capacity=2)
    assert inv.add_item("item_1", -5) is False
    assert inv.remove_item("item_1", 0) is False
"""
    temp_workspace.write(f"{project_dir}/tests/test_inventory.py", inv_test_py)

    # Step 5: Verify feature integration passes
    feature_report = await agent.verify_game(temp_workspace, project_dir, sandbox)
    assert feature_report.success
    assert feature_report.passed_count == 5  # 2 baseline + 3 inventory tests

    # Step 6: Inject non-trivial gameplay defect into systems/inventory.py
    # Off-by-one capacity check: len(self.items) > self.max_capacity allows 1 extra item
    defective_inventory = inventory_py.replace(
        "len(self.items) >= self.max_capacity",
        "len(self.items) > self.max_capacity",
    )
    temp_workspace.write(f"{project_dir}/systems/inventory.py", defective_inventory)

    # Step 7: Verify failure is detected
    failing_report = await agent.verify_game(temp_workspace, project_dir, sandbox)
    assert not failing_report.success
    assert failing_report.failed_count >= 1
    assert "test_inventory_capacity_limit" in failing_report.failed_tests

    # Step 8: Cognitive Diagnosis & Autonomous Repair
    repaired_report = await agent.diagnose_and_repair(
        temp_workspace,
        project_dir,
        sandbox,
        max_iterations=3,
    )

    # Step 9: Verify convergence and repair safety audit
    assert repaired_report.success
    assert repaired_report.failed_count == 0
    assert repaired_report.metadata.get("repaired") is True
    assert repaired_report.repair_audit is not None
    assert repaired_report.repair_audit.test_files_touched is False
    assert repaired_report.repair_audit.tests_weakened is False
    assert "inventory" in repaired_report.repair_audit.hypothesis.lower()

    # Step 10: Invariant confirmation
    repaired_code = temp_workspace.read(f"{project_dir}/systems/inventory.py")["content"]
    assert "len(self.items) >= self.max_capacity" in repaired_code

    # Assert test specification remained untouched
    test_code = temp_workspace.read(f"{project_dir}/tests/test_inventory.py")["content"]
    assert 'assert inv.add_item("item_3", 1) is False' in test_code


@pytest.mark.asyncio
async def test_proof_of_genericity_second_consumer(
    temp_workspace: WorkspaceManager, sandbox: CodeSandbox
) -> None:
    """3. Second consumer (CardDeckGame) proves capabilities are 100% generic."""
    agent = GameDevAgent()
    project_dir = "card_game"

    # Define CardGame state schema evolution
    v1_schema = GameStateSchema(
        version=1,
        fields={"deck": {"type": "list"}, "hand_size": {"type": "int"}},
    )
    v2_schema = GameStateSchema(
        version=2,
        fields={
            "deck": {"type": "list"},
            "hand_size": {"type": "int"},
            "discard_pile": {"type": "list", "default": list},
        },
    )
    diff = agent.evolve_state_schema(v1_schema, v2_schema)
    assert any(a.field_name == "discard_pile" for a in diff.added_fields)

    # Scaffold and verify CardGame domain rules
    deck_py = """import random

class DeckManager:
    def __init__(self, seed: int = 100) -> None:
        self.cards = [f"card_{i}" for i in range(20)]
        random.Random(seed).shuffle(self.cards)
        self.discard = []

    def draw(self) -> str | None:
        if not self.cards:
            return None
        return self.cards.pop()

    def discard_card(self, card: str) -> None:
        self.discard.append(card)
"""
    temp_workspace.write(f"{project_dir}/systems/deck.py", deck_py)

    test_deck_py = """from systems.deck import DeckManager

def test_deck_draw_and_discard():
    deck = DeckManager(seed=42)
    card = deck.draw()
    assert card is not None
    assert len(deck.cards) == 19
    deck.discard_card(card)
    assert len(deck.discard) == 1
"""
    temp_workspace.write(f"{project_dir}/tests/test_deck.py", test_deck_py)

    validation = GameArchitectureValidator.validate_workspace(temp_workspace, project_dir)
    assert validation.is_valid

    report = await agent.verify_game(temp_workspace, project_dir, sandbox)
    assert report.success
    assert report.passed_count == 1
