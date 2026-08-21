"""Tests for domain learner types."""

from __future__ import annotations

import pytest
from datetime import datetime

from app.domain.learner import (
    LearnerState,
    MasteryScore,
    PedagogicalTurn,
    MisconceptionState,
    MisconceptionType,
    TutoringMode,
    Evaluation,
    EvaluationResult,
)


class TestMasteryScore:
    def test_default_creation(self):
        ms = MasteryScore(concept_id="lhs:phys.force")
        assert ms.concept_id == "lhs:phys.force"
        assert ms.score == 0.0
        assert ms.confidence == 1.0
        assert ms.practice_count == 0
        assert ms.correct_count == 0

    def test_is_mastered(self):
        ms = MasteryScore(concept_id="test", score=0.9)
        assert ms.is_mastered() is True
        ms2 = MasteryScore(concept_id="test", score=0.7)
        assert ms2.is_mastered() is False

    def test_with_attempt_correct(self):
        ms = MasteryScore(concept_id="test", score=0.5, practice_count=2, correct_count=1)
        updated = ms.with_attempt(True)
        assert updated.practice_count == 3
        assert updated.correct_count == 2
        assert updated.score == 2/3

    def test_with_attempt_incorrect(self):
        ms = MasteryScore(concept_id="test", score=0.5, practice_count=2, correct_count=1)
        updated = ms.with_attempt(False)
        assert updated.practice_count == 3
        assert updated.correct_count == 1
        assert updated.score == 1/3


class TestMisconceptionState:
    def test_default_creation(self):
        ms = MisconceptionState(
            learner_id="learner1",
            concept_id="lhs:phys.force",
            misconception=MisconceptionType.HEAVIER_FALLS_FASTER,
        )
        assert ms.learner_id == "learner1"
        assert ms.concept_id == "lhs:phys.force"
        assert ms.misconception == MisconceptionType.HEAVIER_FALLS_FASTER
        assert ms.resolved is False
        assert ms.occurrences == 1

    def test_with_occurrence(self):
        ms = MisconceptionState(
            learner_id="l1", concept_id="c1", misconception=MisconceptionType.HEAVIER_FALLS_FASTER
        )
        updated = ms.with_occurrence()
        assert updated.occurrences == 2
        assert updated.resolved is False

    def test_mark_resolved(self):
        ms = MisconceptionState(
            learner_id="l1", concept_id="c1", misconception=MisconceptionType.HEAVIER_FALLS_FASTER
        )
        resolved = ms.mark_resolved("socratic_resolution")
        assert resolved.resolved is True
        assert resolved.resolution_method == "socratic_resolution"
        assert resolved.resolved_at is not None


class TestEvaluation:
    def test_is_correct(self):
        eval_correct = Evaluation(result=EvaluationResult.CORRECT, score=1.0, feedback="Good!")
        assert eval_correct.is_correct is True

        eval_incorrect = Evaluation(result=EvaluationResult.INCORRECT, score=0.0, feedback="Wrong")
        assert eval_incorrect.is_correct is False

    def test_needs_scaffolding(self):
        for result in (
            EvaluationResult.PARTIAL,
            EvaluationResult.INCORRECT,
            EvaluationResult.MISCONCEPTION_DETECTED,
        ):
            eval_obj = Evaluation(result=result, score=0.5, feedback="")
            assert eval_obj.needs_scaffolding is True

        eval_correct = Evaluation(result=EvaluationResult.CORRECT, score=1.0, feedback="")
        assert eval_correct.needs_scaffolding is False


class TestPedagogicalTurn:
    def test_creation(self):
        turn = PedagogicalTurn(
            learner_id="l1",
            mode=TutoringMode.SOCRATIC_MENTOR,
            concept_id="lhs:phys.force",
            prompt="What is force?",
            response="Force is mass times acceleration",
        )
        assert turn.learner_id == "l1"
        assert turn.mode == TutoringMode.SOCRATIC_MENTOR
        assert turn.concept_id == "lhs:phys.force"

    def test_turn_id_auto_generated(self):
        turn = PedagogicalTurn(learner_id="l1", mode=TutoringMode.SOCRATIC_MENTOR)
        assert turn.turn_id.startswith("turn-")


class TestLearnerState:
    def test_get_mastery(self):
        ms = MasteryScore(concept_id="lhs:phys.force", score=0.9)
        state = LearnerState(learner_id="l1", mastery={"lhs:phys.force": ms})
        assert state.get_mastery("lhs:phys.force") == ms
        assert state.get_mastery("lhs:phys.mass") is None

    def test_get_misconception(self):
        misc = MisconceptionState(
            learner_id="l1", concept_id="c1", misconception=MisconceptionType.HEAVIER_FALLS_FASTER
        )
        state = LearnerState(learner_id="l1", misconceptions={"c1": misc})
        assert state.get_misconception("c1") == misc
        assert state.get_misconception("c2") is None
        # Resolved misconception not returned
        resolved_misc = MisconceptionState(learner_id="l1", concept_id="c1", misconception=MisconceptionType.HEAVIER_FALLS_FASTER).mark_resolved("test")
        state2 = LearnerState(learner_id="l1", misconceptions={"c1": resolved_misc})
        assert state2.get_misconception("c1") is None

    def test_is_ready_for(self):
        ms1 = MasteryScore(concept_id="prereq1", score=0.9)
        ms2 = MasteryScore(concept_id="prereq2", score=0.9)
        state = LearnerState(learner_id="l1", mastery={"prereq1": ms1, "prereq2": ms2})
        assert state.is_ready_for("target", ("prereq1", "prereq2"), 0.85) is True
        assert state.is_ready_for("target", ("prereq1", "prereq2"), 0.95) is False
        assert state.is_ready_for("target", ("missing",), 0.5) is False

    def test_update_mastery_new(self):
        state = LearnerState(learner_id="l1")
        updated = state.update_mastery("new_concept", True)
        assert updated.mastery["new_concept"].score == 1.0
        assert updated.mastery["new_concept"].practice_count == 1
        assert updated.mastery["new_concept"].correct_count == 1

    def test_update_mastery_existing(self):
        ms = MasteryScore(concept_id="c1", score=0.5, practice_count=2, correct_count=1)
        state = LearnerState(learner_id="l1", mastery={"c1": ms})
        updated = state.update_mastery("c1", True)
        assert updated.mastery["c1"].practice_count == 3
        assert updated.mastery["c1"].correct_count == 2

    def test_record_misconception_new(self):
        state = LearnerState(learner_id="l1")
        updated = state.record_misconception("c1", MisconceptionType.HEAVIER_FALLS_FASTER)
        assert "c1" in updated.misconceptions
        assert updated.misconceptions["c1"].occurrences == 1

    def test_record_misconception_increments(self):
        misc = MisconceptionState(learner_id="l1", concept_id="c1", misconception=MisconceptionType.HEAVIER_FALLS_FASTER)
        state = LearnerState(learner_id="l1", misconceptions={"c1": misc})
        updated = state.record_misconception("c1", MisconceptionType.HEAVIER_FALLS_FASTER)
        assert updated.misconceptions["c1"].occurrences == 2

    def test_resolve_misconception(self):
        misc = MisconceptionState(learner_id="l1", concept_id="c1", misconception=MisconceptionType.HEAVIER_FALLS_FASTER)
        state = LearnerState(learner_id="l1", misconceptions={"c1": misc})
        updated = state.resolve_misconception("c1", "socratic")
        assert updated.misconceptions["c1"].resolved is True
        assert updated.misconceptions["c1"].resolution_method == "socratic_resolution"

    def test_add_turn(self):
        state = LearnerState(learner_id="l1")
        turn_id = "turn-123"
        updated = state.add_turn(turn_id)
        assert turn_id in updated.dialogue_history

    def test_set_active_concept(self):
        state = LearnerState(learner_id="l1")
        updated = state.set_active_concept("lhs:phys.force")
        assert updated.active_concept == "lhs:phys.force"

    def test_set_mode(self):
        state = LearnerState(learner_id="l1")
        updated = state.set_mode("exam_drill")
        assert updated.current_mode == "exam_drill"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
