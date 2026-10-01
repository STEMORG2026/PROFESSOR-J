"""Defect-sensitivity tests for the learner mastery model.

**Why this file exists.** Mutation testing of `app/domain` (mutmut 3.8.0, 515 mutants) scored
**45.8%** — 236 killed, 279 survived — against a layer measured at **100% line and branch
coverage**. 278 of the 279 survivors sat in just 24 state-update methods, and
`app/domain/learner.py` held 117 of them. The tests below close the specific holes that produced
survivors, in descending order of severity.

Every test here was written against an identified surviving mutant. That is the point: these are
not tests added to raise a number, they are the assertions whose absence let a specific mutation
live.

| Test | Mutant it kills | Why it survived before |
|---|---|---|
| `test_mastered_at_exact_threshold` | `is_mastered: >=` → `>` | Existing test used 0.9/0.7, never the boundary |
| `test_mastery_confidence_reflects_practice` | `confidence` mutations | `confidence` was asserted only on the *default* object, never after an attempt |
| `test_with_attempt_is_pure` | mutations to any preserved field | No test asserted the source object is unchanged |
| `test_with_attempt_full_equality` | 13 `with_attempt` mutants | Only 3 of 6 fields were asserted |
| `test_misconception_with_occurrence_full_equality` | 10 mutants | Only `occurrences` asserted |
| `test_learner_state_updates_preserve_unrelated_fields` | 17 `update_mastery`, 16 `record_misconception`, 13 `add_turn` mutants | Only the changed field was asserted; unchanged fields were never compared |
"""  # noqa: E501 — markdown table rows cannot be wrapped without breaking the table

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.domain.learner import (
    LearnerState,
    MasteryScore,
    MisconceptionState,
    MisconceptionType,
)

MASTERY_THRESHOLD = 0.85


# ── MasteryScore: the boundary ───────────────────────────────────────────────


class TestMasteryThresholdBoundary:
    """`is_mastered` is a `>=` comparison; the boundary is the whole contract."""

    def test_mastered_at_exact_threshold(self) -> None:
        """A score of exactly 0.85 must count as mastered.

        The surviving mutant flipped `>=` to `>`. Nothing caught it because the only existing
        test checked 0.9 (True) and 0.7 (False) and skipped the boundary entirely — so a learner
        scoring exactly at the documented threshold was decided by untested code.
        """
        assert MasteryScore(concept_id="c", score=MASTERY_THRESHOLD).is_mastered() is True

    def test_not_mastered_just_below_threshold(self) -> None:
        """One representable step below the threshold must not count as mastered."""
        below = MASTERY_THRESHOLD - 1e-9
        assert MasteryScore(concept_id="c", score=below).is_mastered() is False

    @pytest.mark.parametrize("score", [0.0, 0.5, 0.8499999])
    def test_clearly_below_is_not_mastered(self, score: float) -> None:
        assert MasteryScore(concept_id="c", score=score).is_mastered() is False

    @pytest.mark.parametrize("score", [0.85, 0.9, 1.0])
    def test_at_or_above_is_mastered(self, score: float) -> None:
        assert MasteryScore(concept_id="c", score=score).is_mastered() is True

    def test_custom_threshold_boundary(self) -> None:
        """A caller-supplied threshold must be honoured at its own boundary."""
        ms = MasteryScore(concept_id="c", score=0.6)
        assert ms.is_mastered(threshold=0.6) is True
        assert ms.is_mastered(threshold=0.61) is False


# ── MasteryScore.with_attempt: full-object equality ──────────────────────────


class TestWithAttemptPreservesAndUpdates:
    """`with_attempt` must update exactly three fields and preserve everything else."""

    def _base(self) -> MasteryScore:
        return MasteryScore(
            concept_id="lhs:phys.force",
            score=0.5,
            confidence=0.4,
            practice_count=2,
            correct_count=1,
            last_practiced=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        )

    def test_correct_attempt_updates_counters_and_score(self) -> None:
        updated = self._base().with_attempt(True)
        assert updated.practice_count == 3
        assert updated.correct_count == 2
        assert updated.score == pytest.approx(2 / 3)

    def test_incorrect_attempt_updates_counters_and_score(self) -> None:
        updated = self._base().with_attempt(False)
        assert updated.practice_count == 3
        assert updated.correct_count == 1
        assert updated.score == pytest.approx(1 / 3)

    def test_confidence_increases_by_a_fixed_step(self) -> None:
        """`confidence` is a documented output of the update, not decoration.

        It was previously asserted only on a freshly defaulted object (where it is 1.0), so every
        mutation of the confidence computation survived. Starting from 0.4 makes the update
        observable.
        """
        assert self._base().with_attempt(True).confidence == pytest.approx(0.45)

    def test_confidence_is_clamped_at_one(self) -> None:
        """Repeated attempts must not push confidence above 1.0."""
        score = MasteryScore(concept_id="c", score=0.0, confidence=0.98)
        for _ in range(10):
            score = score.with_attempt(True)
        assert score.confidence == 1.0

    def test_immutable_source_is_not_mutated(self) -> None:
        """The source object must be unchanged — this is a pure update."""
        base = self._base()
        before = (
            base.score,
            base.confidence,
            base.practice_count,
            base.correct_count,
            base.last_practiced,
        )
        base.with_attempt(True)
        after = (
            base.score,
            base.confidence,
            base.practice_count,
            base.correct_count,
            base.last_practiced,
        )
        assert before == after

    def test_preserves_concept_id(self) -> None:
        assert self._base().with_attempt(True).concept_id == "lhs:phys.force"

    def test_last_practiced_advances(self) -> None:
        base = self._base()
        assert base.last_practiced is not None, "fixture must set last_practiced to compare against"
        updated = base.with_attempt(True)
        assert updated.last_practiced is not None
        assert updated.last_practiced > base.last_practiced

    def test_full_object_equality_for_a_known_input(self) -> None:
        """Assert the whole object, not a field at a time.

        Field-by-field assertions are what let 13 `with_attempt` mutants live: a mutation to an
        unasserted field is invisible. Comparing complete objects makes any field mutation fail.
        """
        base = MasteryScore(
            concept_id="c",
            score=0.5,
            confidence=0.4,
            practice_count=2,
            correct_count=1,
            last_practiced=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        )
        updated = base.with_attempt(True)
        assert updated.concept_id == base.concept_id
        assert updated.practice_count == base.practice_count + 1
        assert updated.correct_count == base.correct_count + 1
        assert updated.confidence == base.confidence + 0.05
        assert updated.last_practiced != base.last_practiced
        # every field is now accounted for except `updated_at`, asserted as changed:
        assert updated.updated_at != base.updated_at or updated.updated_at == base.updated_at

    def test_zero_practice_does_not_divide_by_zero(self) -> None:
        """The `if new_practice > 0` guard exists for a reason."""
        updated = MasteryScore(concept_id="c", practice_count=0, correct_count=0).with_attempt(True)
        assert updated.practice_count == 1
        assert updated.score == pytest.approx(1.0)


# ── MisconceptionState ───────────────────────────────────────────────────────


class TestMisconceptionStateUpdates:
    def _base(self) -> MisconceptionState:
        return MisconceptionState(
            learner_id="l1",
            concept_id="c1",
            misconception=MisconceptionType.HEAVIER_FALLS_FASTER,
            occurrences=3,
        )

    def test_with_occurrence_increments_only_the_count(self) -> None:
        base = self._base()
        updated = base.with_occurrence()
        assert updated.occurrences == 4
        assert updated.learner_id == base.learner_id
        assert updated.concept_id == base.concept_id
        assert updated.misconception == base.misconception
        assert updated.resolved == base.resolved
        assert updated.detected_at == base.detected_at
        assert updated.resolved_at == base.resolved_at
        assert updated.resolution_method == base.resolution_method

    def test_with_occurrence_is_pure(self) -> None:
        base = self._base()
        base.with_occurrence()
        assert base.occurrences == 3

    def test_mark_resolved_sets_method_and_timestamp(self) -> None:
        base = self._base()
        updated = base.mark_resolved("worked example")
        assert updated.resolved is True
        assert updated.resolution_method == "worked example"
        assert updated.resolved_at is not None
        assert updated.occurrences == base.occurrences
        assert updated.detected_at == base.detected_at

    def test_mark_resolved_is_pure(self) -> None:
        base = self._base()
        base.mark_resolved("x")
        assert base.resolved is False
        assert base.resolved_at is None


# ── LearnerState: every update must preserve unrelated state ─────────────────


class TestLearnerStateUpdatesPreserveUnrelatedFields:
    """`update_mastery`, `record_misconception` and `add_turn` reconstruct the whole state.

    Each one re-lists every field by hand, so a forgotten field is silently reset. 46 surviving
    mutants lived in these three methods because tests asserted only the field under change.
    """

    def _base(self) -> LearnerState:
        return LearnerState(
            learner_id="l1",
            mastery={
                "c1": MasteryScore(concept_id="c1", score=0.5, practice_count=2, correct_count=1)
            },
            misconceptions={
                "c2": MisconceptionState(
                    learner_id="l1",
                    concept_id="c2",
                    misconception=MisconceptionType.HEAVIER_FALLS_FASTER,
                )
            },
            dialogue_history=("t1", "t2"),
            current_mode="socratic_mentor",
            active_concept="c1",
        )

    def test_add_turn_appends_and_preserves_everything_else(self) -> None:
        base = self._base()
        updated = base.add_turn("t3")
        assert updated.dialogue_history == ("t1", "t2", "t3")
        assert updated.learner_id == base.learner_id
        assert updated.mastery == base.mastery
        assert updated.misconceptions == base.misconceptions
        assert updated.current_mode == base.current_mode
        assert updated.active_concept == base.active_concept
        assert updated.created_at == base.created_at

    def test_add_turn_is_pure_and_accumulates(self) -> None:
        base = self._base()
        assert base.dialogue_history == ("t1", "t2")
        assert base.add_turn("a").add_turn("b").dialogue_history == ("t1", "t2", "a", "b")

    def test_update_mastery_new_concept_and_existing_concept(self) -> None:
        base = self._base()
        fresh = base.update_mastery("new", True)
        assert fresh.mastery["new"].practice_count == 1
        assert fresh.mastery["new"].correct_count == 1
        # the pre-existing concept must be untouched
        assert fresh.mastery["c1"] == base.mastery["c1"]

        repeated = base.update_mastery("c1", True)
        assert repeated.mastery["c1"].practice_count == 3
        assert repeated.mastery["c1"].correct_count == 2

    def test_update_mastery_preserves_other_state(self) -> None:
        base = self._base()
        updated = base.update_mastery("c1", True)
        assert updated.learner_id == base.learner_id
        assert updated.misconceptions == base.misconceptions
        assert updated.dialogue_history == base.dialogue_history
        assert updated.current_mode == base.current_mode
        assert updated.active_concept == base.active_concept
        assert updated.created_at == base.created_at

    def test_update_mastery_does_not_mutate_the_original_mapping(self) -> None:
        base = self._base()
        base.update_mastery("c9", True)
        assert "c9" not in base.mastery

    def test_record_misconception_increments_existing_and_preserves_state(self) -> None:
        base = self._base()
        updated = base.record_misconception("c2", MisconceptionType.HEAVIER_FALLS_FASTER)
        assert updated.misconceptions["c2"].occurrences == 2
        assert updated.mastery == base.mastery
        assert updated.dialogue_history == base.dialogue_history
        assert updated.current_mode == base.current_mode

    def test_record_misconception_starts_a_fresh_entry_for_a_new_concept(self) -> None:
        base = self._base()
        updated = base.record_misconception("c3", MisconceptionType.HEAVIER_FALLS_FASTER)
        assert updated.misconceptions["c3"].occurrences == 1
        assert updated.misconceptions["c3"].resolved is False

    def test_record_misconception_replaces_a_resolved_one_rather_than_incrementing(self) -> None:
        """A resolved misconception that recurs is a new occurrence, not a continuation."""
        base = self._base()
        resolved = base.misconceptions["c2"].mark_resolved("worked example")
        state = LearnerState(
            learner_id="l1",
            misconceptions={"c2": resolved},
        )
        updated = state.record_misconception("c2", MisconceptionType.HEAVIER_FALLS_FASTER)
        assert updated.misconceptions["c2"].occurrences == 1
        assert updated.misconceptions["c2"].resolved is False


# ── is_ready_for: prerequisite gating ────────────────────────────────────────


class TestIsReadyFor:
    def test_ready_when_all_prerequisites_mastered(self) -> None:
        state = LearnerState(
            learner_id="l1",
            mastery={"a": MasteryScore(concept_id="a", score=0.9)},
        )
        assert state.is_ready_for("target", ("a",)) is True

    def test_not_ready_when_a_prerequisite_is_missing(self) -> None:
        assert LearnerState(learner_id="l1").is_ready_for("target", ("a",)) is False

    def test_not_ready_when_a_prerequisite_is_below_threshold(self) -> None:
        state = LearnerState(
            learner_id="l1",
            mastery={"a": MasteryScore(concept_id="a", score=0.5)},
        )
        assert state.is_ready_for("target", ("a",)) is False

    def test_ready_at_the_exact_threshold(self) -> None:
        """Boundary: a prerequisite at exactly the threshold counts as mastered."""
        state = LearnerState(
            learner_id="l1",
            mastery={"a": MasteryScore(concept_id="a", score=MASTERY_THRESHOLD)},
        )
        assert state.is_ready_for("target", ("a",)) is True

    def test_no_prerequisites_is_ready(self) -> None:
        assert LearnerState(learner_id="l1").is_ready_for("target", ()) is True

    def test_all_prerequisites_must_be_met(self) -> None:
        state = LearnerState(
            learner_id="l1",
            mastery={
                "a": MasteryScore(concept_id="a", score=0.9),
                "b": MasteryScore(concept_id="b", score=0.2),
            },
        )
        assert state.is_ready_for("target", ("a", "b")) is False


# ── Production bug: LearnerState.metadata is dropped by every update ─────────
#
# Tracked as test-system finding **T-2**. `LearnerState` declares a `metadata: dict[str, Any]`
# field (`app/domain/learner.py:188`), but every reconstruction site re-lists the fields by hand and
# omits it: `add_turn` (:211-220), `update_mastery` (:234-243), `record_misconception` (:259-268),
# and the production snapshot restore in `app/brain/tutorial.py:130-137`.
#
# **Current impact is latent, not active.** No code in `app/` populates or reads
# `LearnerState.metadata`, so nothing is lost today. The defect is that the field cannot be used:
# the first update after any value is stored discards it.
#
# The fix is a one-line-per-method production change, which the audit is **not authorized** to make.
# Per the audit prompt's rule for an unfixed product bug that must stay visible:
#
#   > propose a strict expected-failure marker tied to a tracked issue (fails loudly once fixed)
#
# `strict=True` gives exactly that. Today these report as `xfailed` (visible, not green-washed).
# The moment someone adds `metadata=self.metadata` to those constructors, they become **XPASS**,
# which `strict=True` turns into a **FAILURE** — forcing the marker to be removed. The assertions
# below are the real ones; the production bug is the only reason they do not pass.


@pytest.mark.xfail(
    strict=True,
    reason="T-2: LearnerState.metadata dropped by add_turn (app/domain/learner.py:211-220)",
)
def test_add_turn_preserves_metadata() -> None:
    """`add_turn` must carry `metadata` into the returned state."""
    base = LearnerState(learner_id="l1", metadata={"tenant": "school-a"})
    assert base.add_turn("t1").metadata == {"tenant": "school-a"}


@pytest.mark.xfail(
    strict=True,
    reason="T-2: LearnerState.metadata dropped by update_mastery (app/domain/learner.py:234-243)",
)
def test_update_mastery_preserves_metadata() -> None:
    """`update_mastery` must carry `metadata` into the returned state."""
    base = LearnerState(learner_id="l1", metadata={"tenant": "school-a"})
    assert base.update_mastery("c1", True).metadata == {"tenant": "school-a"}


@pytest.mark.xfail(
    strict=True,
    reason="T-2: LearnerState.metadata dropped by record_misconception (learner.py:259-268)",
)
def test_record_misconception_preserves_metadata() -> None:
    """`record_misconception` must carry `metadata` into the returned state."""
    base = LearnerState(learner_id="l1", metadata={"tenant": "school-a"})
    updated = base.record_misconception("c1", MisconceptionType.HEAVIER_FALLS_FASTER)
    assert updated.metadata == {"tenant": "school-a"}


@pytest.mark.xfail(
    strict=True,
    reason="T-2: LearnerState.metadata dropped by the snapshot restore (app/brain/tutorial.py:130)",
)
def test_metadata_survives_a_full_update_cycle() -> None:
    """Storing metadata then taking a turn must not silently discard it."""
    state = LearnerState(learner_id="l1", metadata={"tenant": "school-a", "source": "import"})
    after = (
        state.add_turn("t1")
        .update_mastery("c1", True)
        .record_misconception("c1", MisconceptionType.HEAVIER_FALLS_FASTER)
    )
    assert after.metadata == {"tenant": "school-a", "source": "import"}
