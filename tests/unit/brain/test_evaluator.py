"""Tests for EvaluatorAgent — deterministic rubric scoring + mastery updates."""

from __future__ import annotations

from app.brain.evaluator import EvaluatorAgent
from app.domain.learner import (
    EvaluationResult,
    LearnerState,
    MisconceptionType,
)


def _evaluator() -> EvaluatorAgent:
    return EvaluatorAgent(tolerance=0.01)


class TestRubricScoring:
    def test_correct_numeric_answer(self) -> None:
        ev = _evaluator().evaluate("the force is 120 N", expected=120.0, accept_terms=("f=ma",))
        assert ev.is_correct and ev.result == EvaluationResult.CORRECT
        assert ev.score == 1.0

    def test_incorrect_numeric_answer(self) -> None:
        ev = _evaluator().evaluate("the force is 50 N", expected=120.0)
        assert ev.result == EvaluationResult.INCORRECT
        assert ev.next_hint is not None

    def test_within_tolerance(self) -> None:
        ev = _evaluator().evaluate("120.001", expected=120.0)
        assert ev.is_correct

    def test_correct_equation_only(self) -> None:
        # Right principle, no numeric answer: partial when an answer is expected.
        ev = _evaluator().evaluate("F = m * a", expected=120.0, accept_terms=("f=m*a",))
        assert ev.result == EvaluationResult.PARTIAL

    def test_equation_without_expected_answer_is_correct(self) -> None:
        ev = _evaluator().evaluate("F = m * a", accept_terms=("f=m*a",))
        assert ev.is_correct

    def test_empty_answer_incomplete(self) -> None:
        ev = _evaluator().evaluate("   ")
        assert ev.result == EvaluationResult.INCOMPLETE

    def test_misconception_dominates(self) -> None:
        ev = _evaluator().evaluate(
            "heavier objects fall faster",
            expected=120.0,
            detected_misconception=MisconceptionType.HEAVIER_FALLS_FASTER,
        )
        assert ev.result == EvaluationResult.MISCONCEPTION_DETECTED
        assert MisconceptionType.HEAVIER_FALLS_FASTER in ev.detected_misconceptions

    def test_gibberish_incorrect(self) -> None:
        ev = _evaluator().evaluate("blue elephant shuffle")
        assert ev.result == EvaluationResult.INCORRECT


class TestMasteryApplication:
    def test_correct_attempt_increments_mastery(self) -> None:
        learner = LearnerState(learner_id="stu-1")
        ev = _evaluator().evaluate("120", expected=120.0)
        updated = _evaluator().apply(learner, ev, "lhs:phys.force")
        mastery = updated.get_mastery("lhs:phys.force")
        assert mastery is not None
        assert mastery.practice_count == 1
        assert mastery.correct_count == 1
        assert mastery.is_mastered()  # 1/1 correct = 1.0

    def test_incorrect_attempt_does_not_master(self) -> None:
        learner = LearnerState(learner_id="stu-1")
        ev = _evaluator().evaluate("50", expected=120.0)
        updated = _evaluator().apply(learner, ev, "lhs:phys.force")
        mastery = updated.get_mastery("lhs:phys.force")
        assert mastery is not None
        assert mastery.correct_count == 0
        assert not mastery.is_mastered()

    def test_misconception_is_recorded_on_apply(self) -> None:
        learner = LearnerState(learner_id="stu-1")
        ev = _evaluator().evaluate(
            "heavier objects fall faster",
            detected_misconception=MisconceptionType.HEAVIER_FALLS_FASTER,
        )
        updated = _evaluator().apply(learner, ev, "lhs:phys.force")
        assert updated.get_misconception("lhs:phys.force") is not None
