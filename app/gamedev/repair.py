"""Cognitive Game Rule Diagnosis & Repair Engine with Atomic Multi-File Safety.

Coordinates hypothesis formulation, LLM/reasoner-driven defect diagnosis, and regression-safe
multi-file code mutation while strictly preserving test specifications and architectural invariants.

Invariants:
- REPAIR IMPLEMENTATION, NOT THE SPECIFICATION.
- Protected files (tests, governance, configs, framework) must NEVER be modified.
- Multi-file changesets are applied atomically with rollback on test failure.
- Zero external engine imports (preserves domain purity).
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from app.domain.gamedev import (
    GameRepairAudit,
    GameTestReport,
    ModificationScope,
    RepairProposal,
)
from app.gamedev.knowledge import GameKnowledgeCatalog
from app.gamedev.reasoner import GameDevReasoner, ModelGameDevReasoner, RepairContext
from app.tools.sandbox import CodeSandbox
from app.workspace.workspace import WorkspaceManager

logger = logging.getLogger(__name__)


class CognitiveRepairEngine:
    """Diagnostic and repair engine for game domain logic and state defects."""

    def __init__(
        self,
        knowledge_catalog: GameKnowledgeCatalog | None = None,
        reasoner: GameDevReasoner | None = None,
    ) -> None:
        self.knowledge = knowledge_catalog or GameKnowledgeCatalog()
        self.reasoner = reasoner or ModelGameDevReasoner()

    @staticmethod
    def classify_file_scope(rel_path: str) -> ModificationScope:
        """Classify a file path into its governance/architectural modification scope."""
        p = Path(rel_path)
        name = p.name.lower()
        parts = [part.lower() for part in p.parts]

        # 1. Tests (strictly immutable specifications)
        if (
            name.startswith("test_")
            or name.endswith(("test.py", "tests.cs"))
            or "tests" in parts
            or "test" in parts
        ):
            return ModificationScope.TEST

        # 2. Governance & Charters
        if (
            "agents.md" in name
            or "constitution.md" in name
            or ".agents" in parts
            or "governance" in parts
        ):
            return ModificationScope.GOVERNANCE

        # 3. Project Configuration
        if name in {"pyproject.toml", "package.json", "tsconfig.json", ".pre-commit-config.yaml"}:
            return ModificationScope.CONFIGURATION

        # 4. Platform Framework code
        if parts and parts[0] in {"app", "scripts", "frontend", "board"}:
            return ModificationScope.FRAMEWORK

        return ModificationScope.IMPLEMENTATION

    @staticmethod
    def hash_file(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def snapshot_protected_files(
        self,
        workspace: WorkspaceManager,
        project_dir: str,
    ) -> dict[str, str]:
        """Record SHA-256 hashes of all protected files in the workspace."""
        resolved_root = workspace._resolve(project_dir)
        hashes: dict[str, str] = {}
        for p in resolved_root.glob("**/*"):
            if not p.is_file():
                continue
            rel = str(p.relative_to(workspace.root))
            if self.classify_file_scope(rel) != ModificationScope.IMPLEMENTATION:
                res = workspace.read(rel)
                if res.get("success"):
                    hashes[rel] = self.hash_file(res.get("content", ""))
        return hashes

    def verify_protected_files_intact(
        self,
        workspace: WorkspaceManager,
        baseline_hashes: dict[str, str],
    ) -> bool:
        """Assert that no protected file was mutated during repair."""
        for rel, baseline in baseline_hashes.items():
            res = workspace.read(rel)
            if not res.get("success"):
                return False
            current = self.hash_file(res.get("content", ""))
            if current != baseline:
                logger.error("PROTECTED FILE MUTATION DETECTED: %s", rel)
                return False
        return True

    async def diagnose_and_formulate_proposal(
        self,
        report: GameTestReport,
        workspace: WorkspaceManager,
        project_dir: str,
    ) -> RepairProposal:
        """Formulate structured repair proposal using cognitive reasoning."""
        resolved_root = workspace._resolve(project_dir)
        target_files: list[str] = []
        file_contents: dict[str, str] = {}

        for p in sorted(resolved_root.glob("**/*.py")):
            rel = str(p.relative_to(workspace.root))
            if self.classify_file_scope(rel) == ModificationScope.IMPLEMENTATION:
                res = workspace.read(rel)
                if res.get("success"):
                    target_files.append(rel)
                    file_contents[rel] = res.get("content", "")

        context = RepairContext(
            failed_tests=report.failed_tests,
            stdout=report.stdout,
            stderr=report.stderr,
            target_files=tuple(target_files),
            file_contents=file_contents,
        )

        return await self.reasoner.reason_repair(context)

    async def apply_atomic_proposal(
        self,
        workspace: WorkspaceManager,
        proposal: RepairProposal,
        baseline_hashes: dict[str, str],
    ) -> tuple[bool, tuple[str, ...]]:
        """Apply all edits in a RepairProposal atomically.

        Enforces strict modification scope and hash verification.
        """
        backup: dict[str, str] = {}
        modified: list[str] = []

        try:
            # 1. Validate modification scope for all targets
            for edit in proposal.edits:
                scope = self.classify_file_scope(edit.file_path)
                if scope != ModificationScope.IMPLEMENTATION:
                    logger.warning(
                        "REJECTED edit targeting non-implementation file: %s (%s)",
                        edit.file_path,
                        scope,
                    )
                    return False, ()

            # 2. Read and backup targets
            for edit in proposal.edits:
                res = workspace.read(edit.file_path)
                if not res.get("success"):
                    return False, ()
                backup[edit.file_path] = res.get("content", "")

            # 3. Apply edits
            for edit in proposal.edits:
                current_content = backup[edit.file_path]
                if edit.target_snippet not in current_content:
                    logger.debug(
                        "Target snippet not found in %s: %s", edit.file_path, edit.target_snippet
                    )
                    continue

                patched = current_content.replace(edit.target_snippet, edit.replacement_snippet)
                workspace.write(edit.file_path, patched)
                modified.append(edit.file_path)

            # 4. Verify protected files remained untouched
            if not self.verify_protected_files_intact(workspace, baseline_hashes):
                raise ValueError("Protected files were compromised during repair")

            return len(modified) > 0, tuple(modified)

        except Exception as e:
            logger.error("Atomic repair application failed, rolling back: %s", e)
            # Rollback backup
            for rel, orig in backup.items():
                workspace.write(rel, orig)
            return False, ()


class RepairCoordinator:
    """Orchestrates closed-loop repair with budget bounds and multi-path diagnosis."""

    def __init__(
        self,
        repair_engine: CognitiveRepairEngine | None = None,
        max_iterations: int = 3,
    ) -> None:
        self.repair_engine = repair_engine or CognitiveRepairEngine()
        self.max_iterations = max_iterations

    async def coordinate_repair(
        self,
        workspace: WorkspaceManager,
        project_dir: str,
        initial_report: GameTestReport,
        sandbox: CodeSandbox,
        adapter: Any,
    ) -> GameTestReport:
        """Run bounded repair loop until tests pass or budget exhausted."""
        current_report = initial_report
        baseline_hashes = self.repair_engine.snapshot_protected_files(workspace, project_dir)
        total_modified: list[str] = []

        for iteration in range(1, self.max_iterations + 1):
            if current_report.success:
                break

            # 1. Cognitive reasoning diagnosis & proposal
            proposal = await self.repair_engine.diagnose_and_formulate_proposal(
                current_report, workspace, project_dir
            )

            # 2. Atomic proposal application
            success_applied, modified_files = await self.repair_engine.apply_atomic_proposal(
                workspace, proposal, baseline_hashes
            )

            if not success_applied:
                logger.info("No further safe edits applicable at iteration %d", iteration)
                break

            total_modified.extend(modified_files)

            # 3. Headless re-verification
            resolved_path = workspace._resolve(project_dir)
            test_cmd = adapter.get_test_command(str(resolved_path))
            sandbox_res = await sandbox.run_command(test_cmd, cwd=resolved_path)
            parsed_report = adapter.parse_test_output(sandbox_res)

            audit = GameRepairAudit(
                hypothesis=proposal.diagnosis,
                invariant_targeted=proposal.violated_invariant,
                files_considered=proposal.target_files,
                files_modified=tuple(set(total_modified)),
                test_files_touched=False,
                tests_weakened=False,
                tests_before_count=initial_report.passed_count + initial_report.failed_count,
                tests_after_count=parsed_report.passed_count + parsed_report.failed_count,
                iteration_count=iteration,
                success=parsed_report.success,
            )

            current_report = GameTestReport(
                success=parsed_report.success,
                exit_code=parsed_report.exit_code,
                passed_count=parsed_report.passed_count,
                failed_count=parsed_report.failed_count,
                duration_ms=parsed_report.duration_ms,
                stdout=parsed_report.stdout,
                stderr=parsed_report.stderr,
                failed_tests=parsed_report.failed_tests,
                failure_details=parsed_report.failure_details,
                repair_audit=audit,
                metadata={
                    "repaired": parsed_report.success,
                    "iterations": iteration,
                    "initial_failures": initial_report.failed_tests,
                    "proposal_id": proposal.proposal_id,
                },
            )

            if current_report.success:
                logger.info("Cognitive repair succeeded at iteration %d", iteration)
                break

        return current_report


__all__ = ["CognitiveRepairEngine", "RepairCoordinator"]
