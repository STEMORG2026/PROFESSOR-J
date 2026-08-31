"""Unit tests for GameArchitectureValidator."""

import tempfile
from collections.abc import Generator

import pytest

from app.domain.gamedev import EngineTarget, GameArchitecturePattern
from app.gamedev.validator import GameArchitectureValidator
from app.workspace.workspace import WorkspaceManager


@pytest.fixture
def temp_workspace() -> Generator[WorkspaceManager, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield WorkspaceManager(tmpdir)


def test_validator_clean_pure_core(temp_workspace: WorkspaceManager) -> None:
    temp_workspace.write("game/Core/Rules.cs", "namespace Game.Core;\npublic class Rules {}")
    temp_workspace.write("game/Tests/RulesTests.cs", "namespace Game.Tests;\npublic class Tests {}")

    report = GameArchitectureValidator.validate_workspace(
        temp_workspace,
        project_dir="game",
        pattern=GameArchitecturePattern.PURE_CORE_HEADLESS,
        target=EngineTarget.PURE_CORE,
    )

    assert report.is_valid
    assert report.error_count == 0


def test_validator_catches_prohibited_unity_import(temp_workspace: WorkspaceManager) -> None:
    temp_workspace.write(
        "game/Core/Rules.cs",
        "using UnityEngine;\nnamespace Game.Core;\npublic class Rules : MonoBehaviour {}",
    )
    temp_workspace.write("game/Tests/RulesTests.cs", "namespace Game.Tests;\npublic class Tests {}")

    report = GameArchitectureValidator.validate_workspace(
        temp_workspace,
        project_dir="game",
        pattern=GameArchitecturePattern.PURE_CORE_HEADLESS,
        target=EngineTarget.PURE_CORE,
    )

    assert not report.is_valid
    assert report.error_count == 1
    assert "UnityEngine" in report.violations[0].message
    assert report.violations[0].line_number == 1


def test_validator_warns_on_missing_tests(temp_workspace: WorkspaceManager) -> None:
    temp_workspace.write("game/Core/Rules.cs", "namespace Game.Core;\npublic class Rules {}")

    report = GameArchitectureValidator.validate_workspace(
        temp_workspace,
        project_dir="game",
        pattern=GameArchitecturePattern.PURE_CORE_HEADLESS,
        target=EngineTarget.PURE_CORE,
    )

    assert report.is_valid  # Warnings do not invalidate
    assert report.warning_count == 1
    assert "missing_test_suite" in [w.rule_name for w in report.warnings]
