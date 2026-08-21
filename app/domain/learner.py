"""Learner Domain Models — Pedagogical state, mastery, and evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class TutoringMode(str, Enum):
    """Tutoring interaction modes."""

    SOCRATIC_MENTOR = "socratic_mentor"      # Diagnose, scaffold, guide
    EXPOSITORY_LECTURE = "expository_lecture"  # Direct explanation
    EXAM_DRILL = "exam_drill"                # Practice problems, timed
    RESEARCH_ADVISOR = "research_advisor"     # Literature synthesis, citations


class MisconceptionType(str, Enum):
    """Catalog of common STEM misconceptions."""

    # Physics
    VELOCITY_ACCELERATION_SAME_DIRECTION = "velocity_acceleration_same_direction"
    ACCELERATION_ALWAYS_SPEEDING_UP = "acceleration_always_speeding_up"
    ZERO_VELOCITY_ZERO_ACCELERATION = "zero_velocity_zero_acceleration"
    CONSTANT_SPEED_ZERO_ACCELERATION = "constant_speed_zero_acceleration"
    FORCE_VELOCITY_SAME_DIRECTION = "force_velocity_same_direction"
    HEAVIER_FALLS_FASTER = "heavier_falls_faster"
    ACTION_REACTION_CANCEL = "action_reaction_cancel"

    # Math
    VARIABLE_AS_LABEL = "variable_as_label"
    EQUALS_AS_OPERATION = "equals_as_operation"
    NEGATIVE_NUMBERS_SMALLER = "negative_numbers_smaller"
    FRACTION_LARGER_DENOMINATOR = "fraction_larger_denominator"

    # General
    CORRELATION_IMPLIES_CAUSATION = "correlation_implies_causation"
    ANECDOTE_AS_EVIDENCE = "anecdote_as_evidence"


class EvaluationResult(str, Enum):
    """Result of a step evaluation."""

    CORRECT = "correct"
    PARTIAL = "partial"
    INCORRECT = "incorrect"
    MISCONCEPTION_DETECTED = "misconception_detected"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True, slots=True)
class Evaluation:
    """Result of evaluating a learner's response or step."""

    result: EvaluationResult
    score: float  # 0.0 to 1.0
    feedback: str
    detected_misconceptions: tuple[MisconceptionType, ...] = field(default_factory=tuple)
    correct_steps: tuple[str, ...] = field(default_factory=tuple)
    incorrect_steps: tuple[str, ...] = field(default_factory=tuple)
    next_hint: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_correct(self) -> bool:
        return self.result == EvaluationResult.CORRECT

    @property
    def needs_scaffolding(self) -> bool:
        return self.result in (
            EvaluationResult.PARTIAL,
            EvaluationResult.INCORRECT,
            EvaluationResult.MISCONCEPTION_DETECTED,
        )


@dataclass(frozen=True, slots=True)
class MasteryScore:
    """Mastery score for a single concept."""

    concept_id: str  # e.g., "lhs:phys.force"
    score: float = 0.0  # 0.0 to 1.0 (BKT/IRT estimate)
    confidence: float = 1.0  # Confidence in the estimate
    practice_count: int = 0
    correct_count: int = 0
    last_practiced: datetime | None = None
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def is_mastered(self, threshold: float = 0.85) -> bool:
        return self.score >= threshold

    def with_attempt(self, correct: bool) -> MasteryScore:
        """Return updated mastery after an attempt (simplified BKT update)."""
        new_practice = self.practice_count + 1
        new_correct = self.correct_count + (1 if correct else 0)
        new_score = new_correct / new_practice if new_practice > 0 else 0.0
        return MasteryScore(
            concept_id=self.concept_id,
            score=new_score,
            confidence=min(1.0, self.confidence + 0.05),
            practice_count=new_practice,
            correct_count=new_correct,
            last_practiced=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )


@dataclass(frozen=True, slots=True)
class PedagogicalTurn:
    """A single turn in a tutoring dialogue."""

    learner_id: str
    mode: TutoringMode
    turn_id: str = field(default_factory=lambda: f"turn-{uuid4().hex[:8]}")
    concept_id: str | None = None  # Target concept
    prompt: str = ""
    response: str = ""
    evaluation: Evaluation | None = None
    mastery_before: dict[str, MasteryScore] = field(default_factory=dict)
    mastery_after: dict[str, MasteryScore] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MisconceptionState:
    """Tracked misconception for a learner on a specific concept."""

    learner_id: str
    concept_id: str
    misconception: MisconceptionType
    resolved: bool = False
    detected_at: datetime = field(default_factory=datetime.utcnow)
    occurrences: int = 1
    resolved_at: datetime | None = None
    resolution_method: str | None = None

    def with_occurrence(self) -> MisconceptionState:
        """Return new state with incremented occurrence count."""
        return MisconceptionState(
            learner_id=self.learner_id,
            concept_id=self.concept_id,
            misconception=self.misconception,
            resolved=self.resolved,
            detected_at=self.detected_at,
            occurrences=self.occurrences + 1,
            resolved_at=self.resolved_at,
            resolution_method=self.resolution_method,
        )

    def mark_resolved(self, method: str) -> MisconceptionState:
        """Return new state marked as resolved."""
        return MisconceptionState(
            learner_id=self.learner_id,
            concept_id=self.concept_id,
            misconception=self.misconception,
            resolved=True,
            detected_at=self.detected_at,
            occurrences=self.occurrences,
            resolved_at=datetime.utcnow(),
            resolution_method=method,
        )


@dataclass(frozen=True, slots=True)
class LearnerState:
    """
    Complete pedagogical state for a learner.

    Tracks mastery, misconceptions, dialogue history, and session context.
    """

    learner_id: str
    mastery: dict[str, MasteryScore] = field(default_factory=dict)  # concept_id -> MasteryScore
    misconceptions: dict[str, MisconceptionState] = field(default_factory=dict)  # concept_id -> MisconceptionState
    dialogue_history: tuple[str, ...] = field(default_factory=tuple)  # turn_ids
    current_mode: str = "socratic_mentor"
    active_concept: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_mastery(self, concept_id: str) -> MasteryScore | None:
        """Get mastery score for a concept."""
        return self.mastery.get(concept_id)

    def get_misconception(self, concept_id: str) -> MisconceptionState | None:
        """Get active misconception for a concept."""
        m = self.misconceptions.get(concept_id)
        return m if m and not m.resolved else None

    def is_ready_for(self, concept_id: str, prerequisites: tuple[str, ...], threshold: float = 0.85) -> bool:
        """Check if learner has mastered all prerequisites for a concept."""
        for prereq_id in prerequisites:
            mastery = self.mastery.get(prereq_id)
            if not mastery or not mastery.is_mastered(threshold):
                return False
        return True

    def add_turn(self, turn_id: str) -> "LearnerState":
        """Return new state with added turn to history."""
        return LearnerState(
            learner_id=self.learner_id,
            mastery=self.mastery,
            misconceptions=self.misconceptions,
            dialogue_history=self.dialogue_history + (turn_id,),
            current_mode=self.current_mode,
            active_concept=self.active_concept,
            created_at=self.created_at,
            updated_at=datetime.utcnow(),
        )

    def update_mastery(self, concept_id: str, correct: bool) -> "LearnerState":
        """Return new state with updated mastery for a concept."""
        current = self.mastery.get(concept_id)
        updated = current.with_attempt(correct) if current else MasteryScore(
            concept_id=concept_id,
            score=0.0,
        ).with_attempt(correct)
        new_mastery = {**self.mastery, concept_id: updated}
        return LearnerState(
            learner_id=self.learner_id,
            mastery=new_mastery,
            misconceptions=self.misconceptions,
            dialogue_history=self.dialogue_history,
            current_mode=self.current_mode,
            active_concept=self.active_concept,
            created_at=self.created_at,
            updated_at=datetime.utcnow(),
        )

    def record_misconception(self, concept_id: str, misconception: MisconceptionType) -> "LearnerState":
        """Record a detected misconception."""
        existing = self.misconceptions.get(concept_id)
        if existing and existing.misconception == misconception and not existing.resolved:
            updated = existing.with_occurrence()
        else:
            updated = MisconceptionState(
                learner_id=self.learner_id,
                concept_id=concept_id,
                misconception=misconception,
            )
        new_misconceptions = {**self.misconceptions, concept_id: updated}
        return LearnerState(
            learner_id=self.learner_id,
            mastery=self.mastery,
            misconceptions=new_misconceptions,
            dialogue_history=self.dialogue_history,
            current_mode=self.current_mode,
            active_concept=self.active_concept,
            created_at=self.created_at,
            updated_at=datetime.utcnow(),
        )

    def resolve_misconception(self, concept_id: str, method: str) -> "LearnerState":
        """Mark a misconception as resolved."""
        existing = self.misconceptions.get(concept_id)
        if existing and not existing.resolved:
            new_misconceptions = {**self.misconceptions, concept_id: existing.mark_resolved("socratic_resolution")}
            return LearnerState(
                learner_id=self.learner_id,
                mastery=self.mastery,
                misconceptions=new_misconceptions,
                dialogue_history=self.dialogue_history,
                current_mode=self.current_mode,
                active_concept=self.active_concept,
                created_at=self.created_at,
                updated_at=datetime.utcnow(),
            )
        return self

    def set_active_concept(self, concept_id: str | None) -> "LearnerState":
        """Set the currently active concept."""
        return LearnerState(
            learner_id=self.learner_id,
            mastery=self.mastery,
            misconceptions=self.misconceptions,
            dialogue_history=self.dialogue_history,
            current_mode=self.current_mode,
            active_concept=concept_id,
            created_at=self.created_at,
            updated_at=datetime.utcnow(),
        )

    def set_mode(self, mode: str) -> "LearnerState":
        """Set the tutoring mode."""
        return LearnerState(
            learner_id=self.learner_id,
            mastery=self.mastery,
            misconceptions=self.misconceptions,
            dialogue_history=self.dialogue_history,
            current_mode=mode,
            active_concept=self.active_concept,
            created_at=self.created_at,
            updated_at=datetime.utcnow(),
        )
