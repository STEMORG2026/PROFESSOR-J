"""Game Architecture Validator — Enforces domain purity and architectural invariants."""

from __future__ import annotations

import logging
import re

from app.domain.gamedev import (
    EngineTarget,
    GameArchitecturePattern,
    GameRuleViolation,
    GameValidationReport,
)
from app.gamedev.patterns import GamePatternCatalog
from app.workspace.workspace import WorkspaceManager

logger = logging.getLogger(__name__)


class GameArchitectureValidator:
    """Validates game project structures against architectural patterns."""

    @classmethod
    def validate_workspace(
        cls,
        workspace: WorkspaceManager,
        project_dir: str = "",
        pattern: GameArchitecturePattern = GameArchitecturePattern.PURE_CORE_HEADLESS,
        target: EngineTarget = EngineTarget.PURE_CORE,
    ) -> GameValidationReport:
        """Validate all files in a project workspace directory.

        Args:
            workspace: WorkspaceManager managing the filesystem.
            project_dir: Relative subfolder of the project.
            pattern: Architectural pattern to validate against.
            target: Engine target.

        Returns:
            GameValidationReport with violations, warnings, and overall status.
        """
        violations: list[GameRuleViolation] = []
        warnings: list[GameRuleViolation] = []

        pattern_def = GamePatternCatalog.get_pattern(pattern)

        # Discover all files in project_dir
        base_path = workspace.root / project_dir if project_dir else workspace.root
        if not base_path.exists():
            return GameValidationReport(
                is_valid=False,
                violations=(
                    GameRuleViolation(
                        rule_name="project_exists",
                        file_path=project_dir or ".",
                        message=f"Project directory does not exist: {project_dir}",
                        severity="error",
                    ),
                ),
                summary="Validation FAIL: Project directory does not exist.",
            )

        all_files: list[str] = []
        for p in base_path.glob("**/*"):
            if p.is_file():
                rel = str(p.relative_to(workspace.root))
                all_files.append(rel)

        core_files = [f for f in all_files if "Core" in f or "rules" in f or "domain" in f]
        test_files = [f for f in all_files if "Test" in f or "tests" in f or f.startswith("test_")]

        # 1. Check prohibited imports in Core rules files
        for fpath in core_files:
            res = workspace.read(fpath)
            if not res.get("success"):
                continue
            content = res.get("content", "")

            for prohibited in pattern_def.prohibited_core_imports:
                csharp_pattern = re.compile(rf"^\s*using\s+{re.escape(prohibited)}", re.MULTILINE)
                python_pattern = re.compile(
                    rf"^\s*(?:import|from)\s+{re.escape(prohibited)}", re.MULTILINE
                )

                for line_no, line in enumerate(content.splitlines(), 1):
                    if csharp_pattern.search(line) or python_pattern.search(line):
                        violations.append(
                            GameRuleViolation(
                                rule_name="domain_purity",
                                file_path=fpath,
                                line_number=line_no,
                                message=(
                                    f"Prohibited import '{prohibited}' in Core file '{fpath}'. "
                                    "Core rules must be pure and independent of engine APIs."
                                ),
                                severity="error",
                            )
                        )

        # 2. Check for presence of test suite
        if not test_files:
            warnings.append(
                GameRuleViolation(
                    rule_name="missing_test_suite",
                    file_path=project_dir or ".",
                    message=(
                        "No test files found in project. " "Headless games require automated tests."
                    ),
                    severity="warning",
                )
            )

        # 3. Check for unseeded random usage in deterministic games
        unseeded_csharp = re.compile(r"new\s+Random\s*\(\s*\)", re.MULTILINE)
        for fpath in core_files:
            res = workspace.read(fpath)
            if not res.get("success"):
                continue
            content = res.get("content", "")

            for line_no, line in enumerate(content.splitlines(), 1):
                if unseeded_csharp.search(line):
                    warnings.append(
                        GameRuleViolation(
                            rule_name="unseeded_random",
                            file_path=fpath,
                            line_number=line_no,
                            message=(
                                f"Unseeded Random() detected at {fpath}:{line_no}. "
                                f"Use deterministic seeded RNG for authoritative rules."
                            ),
                            severity="warning",
                        )
                    )

        is_valid = len(violations) == 0
        summary = (
            f"Validation PASS: 0 errors, {len(warnings)} warnings."
            if is_valid
            else f"Validation FAIL: {len(violations)} errors, {len(warnings)} warnings."
        )

        return GameValidationReport(
            is_valid=is_valid,
            violations=tuple(violations),
            warnings=tuple(warnings),
            architecture_pattern=pattern,
            engine_target=target,
            summary=summary,
        )


__all__ = ["GameArchitectureValidator"]
