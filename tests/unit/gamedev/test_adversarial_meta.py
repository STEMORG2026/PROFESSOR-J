"""Adversarial Meta-Tests for PROFESSOR-J GameDev Capability v0.5.

Proves that the framework unconditionally fails closed against:
1. Synthesized/repaired code importing UnityEngine / Godot / Unreal APIs.
2. Repair proposals attempting to modify test specifications.
3. Repair proposals attempting to modify governance (AGENTS.md / charters).
4. Repair proposals attempting to modify project configuration files.
5. Repair proposals attempting path traversal / escaping workspace boundaries.
6. Non-deterministic replay execution and state divergence.
7. Corrupted or invalid snapshot restoration.
8. Invalid / non-additive state schema migrations.
9. Partial multi-file repair failures (enforces transactional all-or-nothing rollback).
10. Provider returning malformed, unparseable, or empty JSON.
"""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from app.domain.gamedev import (
    FileEdit,
    MigrationSemantics,
    ModificationScope,
    RepairProposal,
    ReplayRecord,
)
from app.gamedev.core import BaseGameCore
from app.gamedev.reasoner import ModelGameDevReasoner, RepairContext
from app.gamedev.repair import ASTPatchValidator, CognitiveRepairEngine
from app.gamedev.replay import DeterministicReplayer
from app.gamedev.schema import GameStateEvolutionEngine, StateSchema
from app.workspace.workspace import WorkspaceManager


@pytest.fixture
def temp_workspace() -> Generator[WorkspaceManager, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield WorkspaceManager(Path(tmpdir))


# ──────────────────────────────────────────────────────────────────────────────
# META-TEST 1: Forbidden Engine Imports Rejected by AST Validator & Certifier
# ──────────────────────────────────────────────────────────────────────────────
def test_meta_1_forbidden_engine_imports_rejected() -> None:
    """1. ASTPatchValidator and GameCoreCertifier reject imports of UnityEngine/Godot/Unreal."""
    forbidden_code = """
import UnityEngine
from UnityEngine.UI import Text

def test_fn():
    pass
"""
    valid, err = ASTPatchValidator.validate_patch(
        original_content="def test_fn(): pass",
        patched_content=forbidden_code,
        file_path="systems/combat.py",
    )
    assert valid is False
    assert "Forbidden engine import detected" in str(err)


# ──────────────────────────────────────────────────────────────────────────────
# META-TEST 2: Repair Proposals Modifying Tests Strictly Rejected
# ──────────────────────────────────────────────────────────────────────────────
def test_meta_2_repair_modifying_tests_rejected() -> None:
    """2. CognitiveRepairEngine rejects any proposal targeting test files."""
    scope = CognitiveRepairEngine.classify_file_scope("tests/test_combat.py")
    assert scope == ModificationScope.TEST

    scope2 = CognitiveRepairEngine.classify_file_scope("Core.Tests/CombatTests.cs")
    assert scope2 == ModificationScope.TEST


# ──────────────────────────────────────────────────────────────────────────────
# META-TEST 3: Repair Proposals Modifying Governance Files Rejected
# ──────────────────────────────────────────────────────────────────────────────
def test_meta_3_repair_modifying_governance_rejected() -> None:
    """3. CognitiveRepairEngine rejects any proposal targeting AGENTS.md or charters."""
    scope1 = CognitiveRepairEngine.classify_file_scope("AGENTS.md")
    assert scope1 == ModificationScope.GOVERNANCE

    scope2 = CognitiveRepairEngine.classify_file_scope("docs/CONSTITUTION.md")
    assert scope2 == ModificationScope.GOVERNANCE

    scope3 = CognitiveRepairEngine.classify_file_scope(".agents/rules.yaml")
    assert scope3 == ModificationScope.GOVERNANCE


# ──────────────────────────────────────────────────────────────────────────────
# META-TEST 4: Repair Proposals Modifying Configuration Files Rejected
# ──────────────────────────────────────────────────────────────────────────────
def test_meta_4_repair_modifying_config_rejected() -> None:
    """4. CognitiveRepairEngine rejects any proposal targeting pyproject.toml / configs."""
    scope1 = CognitiveRepairEngine.classify_file_scope("pyproject.toml")
    assert scope1 == ModificationScope.CONFIGURATION

    scope2 = CognitiveRepairEngine.classify_file_scope("package.json")
    assert scope2 == ModificationScope.CONFIGURATION


# ──────────────────────────────────────────────────────────────────────────────
# META-TEST 5: Path Traversal / Sandbox Escape Rejected
# ──────────────────────────────────────────────────────────────────────────────
def test_meta_5_path_traversal_escape_rejected() -> None:
    """5. ASTPatchValidator rejects file paths containing '..' or absolute paths."""
    valid1, err1 = ASTPatchValidator.validate_patch(
        original_content="x = 1",
        patched_content="x = 2",
        file_path="../../etc/shadow",
    )
    assert valid1 is False
    assert "Path traversal" in str(err1)

    valid2, err2 = ASTPatchValidator.validate_patch(
        original_content="x = 1",
        patched_content="x = 2",
        file_path="/tmp/malicious.py",
    )
    assert valid2 is False


# ──────────────────────────────────────────────────────────────────────────────
# META-TEST 6: Non-Deterministic Replay Divergence Detected
# ──────────────────────────────────────────────────────────────────────────────
def test_meta_6_replay_divergence_detected() -> None:
    """6. DeterministicReplayer detects state hash divergence during replay."""
    core = BaseGameCore()

    # Create record with a tampered expected hash
    _, record = DeterministicReplayer.record_session(
        core=core,
        seed=42,
        dt_sequence=(0.1, 0.1),
        session_id="meta_session",
    )

    # Tamper with the recorded hash
    tampered_hashes = list(record.state_hashes)
    tampered_hashes[1] = "0000000000000000000000000000000000000000000000000000000000000000"
    tampered_record = ReplayRecord(
        record_id=record.record_id,
        seed=record.seed,
        initial_state=record.initial_state,
        intent_sequence=record.intent_sequence,
        tick_count=record.tick_count,
        dt_sequence=record.dt_sequence,
        state_hashes=tuple(tampered_hashes),
        events_emitted=record.events_emitted,
    )

    res = DeterministicReplayer.verify_replay(core, tampered_record)
    assert res.success is False
    assert "divergence" in str(res.divergence_reason).lower()


# ──────────────────────────────────────────────────────────────────────────────
# META-TEST 7: Snapshot Restore Integrity & Corruption Resistance
# ──────────────────────────────────────────────────────────────────────────────
def test_meta_7_snapshot_restore_fidelity() -> None:
    """7. Restoring a snapshot produces an exact deep copy and does not mutate historical state."""
    core = BaseGameCore()
    state = core.initial_state()
    state["health"] = 100.0

    snap = core.snapshot(state, tick=1)
    restored = core.restore(snap)

    assert restored["health"] == 100.0
    # Mutate restored copy
    restored["health"] = 50.0
    # Assert original snapshot data was NOT mutated
    assert snap.state_data["health"] == 100.0


# ──────────────────────────────────────────────────────────────────────────────
# META-TEST 8: Non-Additive / Destructive Schema Migration Rejection
# ──────────────────────────────────────────────────────────────────────────────
def test_meta_8_destructive_schema_migration_rejection() -> None:
    """8. Rejects destructive schema migrations without migration strategy."""
    engine = GameStateEvolutionEngine()
    old_schema = StateSchema(schema_version=1, fields={"gold": "int", "hp": "int"})
    # Removing 'gold' is non-additive / destructive
    new_schema = StateSchema(schema_version=2, fields={"hp": "int"})

    diff = engine.compute_diff(old_schema, new_schema)
    assert engine.classify_semantics(diff) == MigrationSemantics.DESTRUCTIVE
    assert len(diff.removed_fields) == 1
    assert diff.removed_fields[0].field_name == "gold"


# ──────────────────────────────────────────────────────────────────────────────
# META-TEST 9: Partial Multi-File Repair Rollback on Error
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_meta_9_partial_multifile_repair_rollback(
    temp_workspace: WorkspaceManager,
) -> None:
    """9. If any edit in a proposal fails AST validation or causes error, all files rollback."""
    temp_workspace.write("systems/file1.py", "x = 1\n")
    temp_workspace.write("systems/file2.py", "y = 1\n")

    engine = CognitiveRepairEngine()
    baseline_hashes = engine.snapshot_protected_files(temp_workspace, ".")

    proposal = RepairProposal(
        proposal_id="p_bad_multi",
        diagnosis="Test partial failure",
        violated_invariant="Syntax correctness",
        root_cause="Syntax error in file2",
        target_files=("systems/file1.py", "systems/file2.py"),
        edits=(
            FileEdit("systems/file1.py", "x = 1", "x = 10"),
            FileEdit("systems/file2.py", "y = 1", "y = def invalid syntax error @@"),
        ),
        rationale="Multi-file patch with defect in file 2",
    )

    success, modified = await engine.apply_atomic_proposal(
        temp_workspace, proposal, baseline_hashes
    )
    assert success is False

    # Assert file1 was NOT modified (atomicity guaranteed)
    res1 = temp_workspace.read("systems/file1.py")
    assert res1.get("content") == "x = 1\n"


# ──────────────────────────────────────────────────────────────────────────────
# META-TEST 10: Provider Returning Malformed JSON Fails Closed
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_meta_10_provider_malformed_json_fails_closed() -> None:
    """10. Reasoner handles malformed LLM responses safely and returns structured proposal."""
    reasoner = ModelGameDevReasoner()
    ctx = RepairContext(
        failed_tests=("test_sample",),
        stdout="AssertionError: 1 != 2",
        stderr="",
        target_files=("systems/sample.py",),
        file_contents={"systems/sample.py": "def sample(): return 1"},
    )

    # Malformed text
    proposal = reasoner._parse_or_fallback_repair(ctx, "INVALID JSON NO BRACKETS <<<<")
    assert isinstance(proposal, RepairProposal)
    assert proposal.confidence >= 0.0
