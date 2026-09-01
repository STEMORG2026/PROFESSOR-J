"""Milestone v0.3 — GameDev Capability Boundary Audit, Project Analyzer & Multi-Genre Proofs.

Verifies:
1. Cryptographic SHA-256 hash proof of specification immutability during repair.
2. GameProjectAnalyzer structural model extraction across multi-genre codebases.
3. Consumer A (Card Game) semantic defect diagnosis & cognitive repair.
4. Consumer B (Real-time Simulation) timestep defect diagnosis & cognitive repair.
5. Repair guardrails & adversarial scope rejection (TEST, GOVERNANCE, FRAMEWORK).
6. State migration semantics classification (ADDITIVE, DESTRUCTIVE, LOSSY, REVERSIBLE).
"""

import hashlib
import tempfile
from collections.abc import Generator

import pytest

from app.domain.gamedev import (
    GameSystemCategory,
    MigrationSemantics,
    ModificationScope,
)
from app.gamedev.agent import GameDevAgent
from app.gamedev.analyzer import GameProjectAnalyzer
from app.gamedev.components import GameComponentCatalog
from app.gamedev.repair import CognitiveRepairEngine
from app.gamedev.schema import GameStateEvolutionEngine, GameStateSchema
from app.tools.sandbox import CodeSandbox
from app.workspace.workspace import WorkspaceManager


@pytest.fixture
def temp_workspace() -> Generator[WorkspaceManager, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield WorkspaceManager(tmpdir)


@pytest.fixture
def sandbox() -> CodeSandbox:
    return CodeSandbox()


def _sha256(content: str) -> str:
    """Calculate SHA-256 hex digest of a string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ──────────────────────────────────────────────────────────────────────────────
# 1. Cryptographic Proof of Specification Immutability
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_cryptographic_specification_immutability_proof(
    temp_workspace: WorkspaceManager, sandbox: CodeSandbox
) -> None:
    """1. Prove that test specifications are never mutated during defect repair."""
    agent = GameDevAgent()
    project_dir = "proof_game"

    impl_code_initial = """
class BoundedCounter:
    def __init__(self, max_val: int = 10):
        self.max_val = max_val
        self.val = 0

    def increment(self) -> bool:
        if self.val >= self.max_val:  # Correct invariant
            return False
        self.val += 1
        return True
"""
    test_code_initial = """
from systems.counter import BoundedCounter

def test_counter_boundary_limit():
    c = BoundedCounter(max_val=2)
    assert c.increment() is True
    assert c.increment() is True
    assert c.increment() is False  # Must reject on 3rd attempt
"""
    temp_workspace.write(f"{project_dir}/systems/counter.py", impl_code_initial)
    temp_workspace.write(f"{project_dir}/tests/test_counter.py", test_code_initial)

    initial_test_hash = _sha256(test_code_initial)
    initial_impl_hash = _sha256(impl_code_initial)

    # Initial run is green
    report1 = await agent.verify_game(temp_workspace, project_dir, sandbox)
    assert report1.success is True

    # Inject boundary defect into implementation
    defective_impl = impl_code_initial.replace(
        "self.val >= self.max_val", "self.val > self.max_val"
    )
    temp_workspace.write(f"{project_dir}/systems/counter.py", defective_impl)

    # Verification detects failure
    report2 = await agent.verify_game(temp_workspace, project_dir, sandbox)
    assert report2.success is False

    # Execute cognitive repair
    repair_report = await agent.diagnose_and_repair(temp_workspace, project_dir, sandbox)
    assert repair_report.success is True
    assert repair_report.repair_audit is not None
    assert repair_report.repair_audit.test_files_touched is False

    # Cryptographic verification: Test hash is IDENTICAL, Implementation hash is FIXED
    test_code_final = temp_workspace.read(f"{project_dir}/tests/test_counter.py")["content"]
    impl_code_final = temp_workspace.read(f"{project_dir}/systems/counter.py")["content"]

    assert _sha256(test_code_final) == initial_test_hash
    assert _sha256(impl_code_final) == initial_impl_hash


# ──────────────────────────────────────────────────────────────────────────────
# 2. GameProjectAnalyzer Structural Model Extraction
# ──────────────────────────────────────────────────────────────────────────────
def test_game_project_analyzer_structural_extraction(temp_workspace: WorkspaceManager) -> None:
    """2. GameProjectAnalyzer extracts structured models from unfamiliar codebases."""
    project_dir = "sample_rpg"

    # Write multiple domain modules
    temp_workspace.write(
        f"{project_dir}/domain/contracts.py",
        """
class PlayerAttackIntent:
    pass

class CombatResolvedEvent:
    pass
""",
    )
    temp_workspace.write(
        f"{project_dir}/systems/combat.py",
        """
class CombatManager:
    schema_version = 2
""",
    )
    temp_workspace.write(
        f"{project_dir}/tests/test_combat.py",
        """
def test_combat():
    pass
""",
    )

    analyzer = GameProjectAnalyzer()
    model = analyzer.analyze_project(temp_workspace, project_dir)

    assert model.project_name == "sample_rpg"
    assert "CombatManager" in model.detected_systems
    assert "PlayerAttackIntent" in model.intent_handlers
    assert "CombatResolvedEvent" in model.events_emitted
    assert any("test_combat.py" in f for f in model.test_files)
    assert any("combat.py" in f for f in model.source_files)
    assert model.schema_version == 2
    assert model.is_pure_core is True


# ──────────────────────────────────────────────────────────────────────────────
# 3. Consumer A: Card Game Semantic Desync & Cognitive Repair
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_consumer_a_card_game_semantic_repair(
    temp_workspace: WorkspaceManager, sandbox: CodeSandbox
) -> None:
    """3. Consumer A (Card Game): Discard desync defect diagnosed & repaired."""
    agent = GameDevAgent()
    project_dir = "card_game_proof"

    deck_py = """
class DeckManager:
    def __init__(self):
        self.cards = [f"card_{i}" for i in range(10)]
        self.discard = []

    def draw(self) -> str | None:
        if not self.cards:
            return None
        return self.cards.pop()

    def discard_card(self, card: str) -> None:
        # BUG: Appending to discard without removing from active cards
        self.discard.append(card)
"""
    temp_workspace.write(f"{project_dir}/systems/deck.py", deck_py)

    test_deck_py = """
from systems.deck import DeckManager

def test_deck_card_conservation_on_discard():
    deck = DeckManager()
    card = deck.cards[0]
    deck.discard_card(card)
    assert len(deck.discard) == 1
    assert card not in deck.cards  # Discarded card cannot remain in draw pile
"""
    temp_workspace.write(f"{project_dir}/tests/test_deck.py", test_deck_py)

    # Initial verify fails due to card conservation bug
    report_fail = await agent.verify_game(temp_workspace, project_dir, sandbox)
    assert report_fail.success is False

    # Repair resolves conservation desync
    report_fixed = await agent.diagnose_and_repair(temp_workspace, project_dir, sandbox)
    assert report_fixed.success is True
    assert report_fixed.failed_count == 0
    assert report_fixed.repair_audit is not None
    assert report_fixed.repair_audit.test_files_touched is False


# ──────────────────────────────────────────────────────────────────────────────
# 4. Consumer B: Real-Time Simulation Timestep & Cognitive Repair
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_consumer_b_simulation_timestep_repair(
    temp_workspace: WorkspaceManager, sandbox: CodeSandbox
) -> None:
    """4. Consumer B (Simulation): Discrete timestep scaling defect diagnosed & repaired."""
    agent = GameDevAgent()
    project_dir = "physics_sim_proof"

    sim_py = """
class ParticleSimulation:
    def __init__(self, dt: float = 0.02):
        self.dt = dt
        self.x = 0.0
        self.vx = 50.0

    def step(self):
        # BUG: Forgot to scale velocity by discrete timestep dt (self.x += self.vx)
        self.x += self.vx
"""
    temp_workspace.write(f"{project_dir}/systems/sim.py", sim_py)

    test_sim_py = """
import pytest
from systems.sim import ParticleSimulation

def test_particle_position_integration():
    sim = ParticleSimulation(dt=0.02)
    sim.step()
    # x = 0 + 50.0 * 0.02 = 1.0
    assert sim.x == pytest.approx(1.0)
"""
    temp_workspace.write(f"{project_dir}/tests/test_sim.py", test_sim_py)

    report_fail = await agent.verify_game(temp_workspace, project_dir, sandbox)
    assert report_fail.success is False

    report_fixed = await agent.diagnose_and_repair(temp_workspace, project_dir, sandbox)
    assert report_fixed.success is True
    assert report_fixed.failed_count == 0
    assert report_fixed.repair_audit is not None
    assert report_fixed.repair_audit.test_files_touched is False


# ──────────────────────────────────────────────────────────────────────────────
# 5. Repair Guardrails & Modification Scope Classification
# ──────────────────────────────────────────────────────────────────────────────
def test_repair_scope_classification_guardrails() -> None:
    """5. Guardrails classify modification targets and reject test/governance/config edits."""
    engine = CognitiveRepairEngine()

    assert engine.classify_file_scope("dice_tactics/tests/test_game.py") == ModificationScope.TEST
    assert engine.classify_file_scope("tests/unit/test_engine.py") == ModificationScope.TEST
    assert engine.classify_file_scope("AGENTS.md") == ModificationScope.GOVERNANCE
    assert engine.classify_file_scope(".agents/rules.md") == ModificationScope.GOVERNANCE
    assert engine.classify_file_scope("pyproject.toml") == ModificationScope.CONFIGURATION
    assert engine.classify_file_scope("app/domain/gamedev.py") == ModificationScope.FRAMEWORK
    assert (
        engine.classify_file_scope("dice_tactics/systems/grid.py")
        == ModificationScope.IMPLEMENTATION
    )


# ──────────────────────────────────────────────────────────────────────────────
# 6. State Migration Semantics Classification
# ──────────────────────────────────────────────────────────────────────────────
def test_state_migration_semantics_classification() -> None:
    """6. Migration semantics are classified into ADDITIVE, DESTRUCTIVE, LOSSY, REVERSIBLE."""
    engine = GameStateEvolutionEngine()

    s1 = GameStateSchema(version=1, fields={"a": {"type": "int"}})
    s2 = GameStateSchema(
        version=2, fields={"a": {"type": "int"}, "b": {"type": "int", "default": 0}}
    )
    s3 = GameStateSchema(version=3, fields={"b": {"type": "int"}})

    # Additive: v1 -> v2
    diff_add = engine.compute_diff(s1, s2)
    assert engine.classify_semantics(diff_add) == MigrationSemantics.ADDITIVE

    # Destructive: v2 -> v3 (field 'a' removed)
    diff_destruct = engine.compute_diff(s2, s3)
    assert engine.classify_semantics(diff_destruct) == MigrationSemantics.DESTRUCTIVE

    # Lossy: v2 -> v1 (reverse version downgrade)
    diff_lossy = engine.compute_diff(s2, s1)
    assert engine.classify_semantics(diff_lossy) == MigrationSemantics.LOSSY


# ──────────────────────────────────────────────────────────────────────────────
# 7. Component Taxonomy Organization
# ──────────────────────────────────────────────────────────────────────────────
def test_component_taxonomy_organization() -> None:
    """7. Reusable components are mapped to clear taxonomy categories."""
    catalog = GameComponentCatalog()

    assert catalog.event_bus().category == GameSystemCategory.CORE
    assert catalog.command_dispatcher().category == GameSystemCategory.CORE
    assert catalog.state_machine().category == GameSystemCategory.STATE
    assert catalog.turn_manager().category == GameSystemCategory.GAMEPLAY
    assert catalog.grid_board().category == GameSystemCategory.SPATIAL
    assert catalog.fixed_timestep().category == GameSystemCategory.SIMULATION
    assert catalog.deck_manager().category == GameSystemCategory.CARD
    assert catalog.ai_minimax().category == GameSystemCategory.AI
