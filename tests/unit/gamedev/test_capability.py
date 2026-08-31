"""Unit tests for the GameDev Capability subsystem: Knowledge, Workflows, and Autonomous Repair."""

import tempfile
from collections.abc import Generator

import pytest

from app.domain.gamedev import (
    EngineTarget,
    GameGenre,
    GameKnowledgeCategory,
    GameProjectSpec,
    GameSystemType,
    GameWorkflowType,
)
from app.gamedev.agent import GameDevAgent
from app.gamedev.components import GameComponentCatalog
from app.gamedev.knowledge import GameKnowledgeCatalog
from app.gamedev.workflows import GameWorkflowEngine
from app.tools.sandbox import CodeSandbox
from app.workspace.workspace import WorkspaceManager


@pytest.fixture
def temp_workspace() -> Generator[WorkspaceManager, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield WorkspaceManager(tmpdir)


@pytest.fixture
def sandbox() -> CodeSandbox:
    return CodeSandbox()


def test_game_knowledge_catalog_lookup_and_search() -> None:
    """1. GameKnowledgeCatalog provides structured queries by ID, category, and semantic tags."""
    catalog = GameKnowledgeCatalog()

    # Direct ID lookup
    topic = catalog.get("pure_core_presentation_separation")
    assert topic is not None
    assert topic.category == GameKnowledgeCategory.ARCHITECTURE
    assert len(topic.key_invariants) >= 2
    assert len(topic.anti_patterns) >= 2
    assert "headless" in topic.tags

    # Category filtering
    state_topics = catalog.get_by_category(GameKnowledgeCategory.STATE_MANAGEMENT)
    assert len(state_topics) >= 2
    assert any(t.topic_id == "game_loop_determinism" for t in state_topics)
    assert any(t.topic_id == "state_machine_fsm" for t in state_topics)

    # Search by tag / keyword
    ai_results = catalog.search("minimax heuristic decision")
    assert len(ai_results) >= 1
    assert ai_results[0].topic_id == "minimax_ai_decision"

    repair_results = catalog.search("repair failing test diagnosis")
    assert len(repair_results) >= 1
    assert any(t.topic_id == "test_driven_game_repair" for t in repair_results)


def test_expanded_component_catalog_specs() -> None:
    """2. Expanded GameComponentCatalog creates structured component specs."""
    inv = GameComponentCatalog.inventory(max_slots=30, max_weight=50.0)
    assert inv.system_type == GameSystemType.INVENTORY
    assert inv.parameters["max_slots"] == 30

    score = GameComponentCatalog.score_manager(initial_score=100)
    assert score.system_type == GameSystemType.SCORING
    assert score.parameters["initial_score"] == 100

    fsm = GameComponentCatalog.state_machine(initial_state="Lobby")
    assert fsm.system_type == GameSystemType.STATE_MACHINE
    assert fsm.parameters["initial_state"] == "Lobby"

    ai = GameComponentCatalog.ai_minimax(depth=4)
    assert ai.system_type == GameSystemType.AI_DECISION
    assert ai.parameters["depth"] == 4

    save = GameComponentCatalog.save_state_manager(format_type="json")
    assert save.system_type == GameSystemType.SAVE_STATE


def test_game_workflow_planning() -> None:
    """3. GameWorkflowEngine formulates structured operational workflows."""
    engine = GameWorkflowEngine()

    # CREATE_GAME
    create_plan = engine.plan_workflow(
        GameWorkflowType.CREATE_GAME,
        goal="Create a 3D deterministic Ludo board game",
        target_engine=EngineTarget.PURE_CORE,
    )
    assert create_plan.workflow_type == GameWorkflowType.CREATE_GAME
    assert len(create_plan.steps) == 5
    assert any(
        c.system_type == GameSystemType.TURN_MANAGER for c in create_plan.required_components
    )
    assert any(c.system_type == GameSystemType.DICE_RNG for c in create_plan.required_components)

    # ADD_FEATURE
    feature_plan = engine.plan_workflow(
        GameWorkflowType.ADD_FEATURE,
        goal="Add an inventory management system",
    )
    assert feature_plan.workflow_type == GameWorkflowType.ADD_FEATURE
    assert len(feature_plan.steps) == 5

    # FIX_BUG
    bug_plan = engine.plan_workflow(
        GameWorkflowType.FIX_BUG,
        goal="Fix off-by-one dice boundary check",
    )
    assert bug_plan.workflow_type == GameWorkflowType.FIX_BUG
    assert len(bug_plan.steps) == 5


@pytest.mark.asyncio
async def test_autonomous_diagnose_and_repair_loop(
    temp_workspace: WorkspaceManager, sandbox: CodeSandbox
) -> None:
    """4. GameDevAgent performs autonomous diagnosis and closed-loop test repair."""
    agent = GameDevAgent()
    spec = GameProjectSpec(
        title="RepairableGame",
        genre=GameGenre.BOARD_GAME,
        target_engine=EngineTarget.PURE_CORE,
        target_language="python",
    )
    agent.scaffold(spec, temp_workspace, "repair_game")

    # Inject an intentional assertion failure
    broken_test = """
def test_movement_state():
    assert 1 == 2, "Illegal move state calculation"
"""
    temp_workspace.write("repair_game/tests/test_broken.py", broken_test)

    # Verify that standard verification fails
    initial_verify = await agent.verify_game(temp_workspace, "repair_game", sandbox)
    assert not initial_verify.success
    assert initial_verify.failed_count >= 1

    # Execute autonomous diagnose and repair loop
    repaired_report = await agent.diagnose_and_repair(
        temp_workspace,
        "repair_game",
        sandbox,
        max_iterations=3,
    )

    # Must converge to green
    assert repaired_report.success
    assert repaired_report.exit_code == 0
    assert repaired_report.failed_count == 0
    assert repaired_report.metadata.get("repaired") is True
    assert "test_movement_state" in repaired_report.metadata.get("initial_failures", ())
