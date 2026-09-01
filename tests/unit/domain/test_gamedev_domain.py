"""Unit tests for pure GameDev domain models."""

from app.domain.gamedev import (
    EngineTarget,
    GameArchitecturePattern,
    GameComponentSpec,
    GameGenre,
    GameProjectSpec,
    GameRuleViolation,
    GameSystemType,
    GameValidationReport,
)


def test_engine_target_values() -> None:
    assert EngineTarget.PURE_CORE.value == "pure_core"
    assert EngineTarget.UNITY.value == "unity"
    assert EngineTarget.GODOT.value == "godot"
    assert EngineTarget.UNREAL.value == "unreal"
    assert EngineTarget.WEB_CANVAS.value == "web_canvas"


def test_game_genre_values() -> None:
    assert GameGenre.BOARD_GAME.value == "board_game"
    assert GameGenre.TURN_BASED_STRATEGY.value == "turn_based_strategy"
    assert GameGenre.EDUCATIONAL_STEM.value == "educational_stem"


def test_game_component_spec() -> None:
    comp = GameComponentSpec(
        name="DiceRNG",
        system_type=GameSystemType.DICE_RNG,
        description="Seeded dice",
        pattern=GameArchitecturePattern.PURE_CORE_HEADLESS,
        parameters={"sides": 6},
    )
    assert comp.name == "DiceRNG"
    assert comp.system_type == GameSystemType.DICE_RNG
    assert comp.parameters["sides"] == 6


def test_game_project_spec_helpers() -> None:
    comp1 = GameComponentSpec(
        name="TurnManager",
        system_type=GameSystemType.TURN_MANAGER,
        description="Turns",
    )
    comp2 = GameComponentSpec(
        name="GridBoard",
        system_type=GameSystemType.GRID_BOARD,
        description="Board",
    )
    project = GameProjectSpec(
        title="LudoCore",
        genre=GameGenre.BOARD_GAME,
        target_engine=EngineTarget.PURE_CORE,
        components=(comp1, comp2),
    )

    assert project.component_names() == ("TurnManager", "GridBoard")
    assert project.has_system(GameSystemType.TURN_MANAGER)
    assert project.has_system(GameSystemType.GRID_BOARD)
    assert not project.has_system(GameSystemType.COMBAT)


def test_game_validation_report() -> None:
    v1 = GameRuleViolation(
        rule_name="domain_purity",
        file_path="Core/Rules.cs",
        line_number=10,
        message="Illegal import",
        severity="error",
    )
    w1 = GameRuleViolation(
        rule_name="missing_test_suite",
        file_path=".",
        message="No tests",
        severity="warning",
    )
    report = GameValidationReport(
        is_valid=False,
        violations=(v1,),
        warnings=(w1,),
        summary="Failed validation",
    )

    assert not report.is_valid
    assert report.error_count == 1
    assert report.warning_count == 1
