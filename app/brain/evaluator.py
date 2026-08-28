"""EvaluatorAgent — deterministic, rule-based assessment of learner responses.

Companion to :class:`~app.brain.professor.ProfessorAgent`. Given a learner's
free-text answer to a concept problem, it produces a domain
:class:`~app.domain.learner.Evaluation` (correct/partial/incorrect/
misconception/incomplete) and updates the learner's master/record.

The rubric is deliberately deterministic (no LLM) so evaluation is reproducible
and unit-testable now. A symbolic step-verifier (SymPy) is Phase 5 work; this
rule-based layer is the fast, predictable core and remains the contract for
mastery updates regardless of how reasoning is later deepened.

Rules consulted, in priority order:
1. A detected misconception overrides the score -> MISCONCEPTION_DETECTED.
2. The final numeric answer must match the expected value (within tolerance).
3. The canonical equation/symbols must appear for CREDIT toward PARTIAL.
4. Empty responses -> INCOMPLETE.
"""

from __future__ import annotations

import re

from app.domain.learner import (
    Evaluation,
    EvaluationResult,
    LearnerState,
    MisconceptionType,
)

# ── Numeric-answer extraction ───────────────────────────────────────────────
# Pulls the last number (integer or decimal, optional sign) out of free text,
# e.g. "the force is 120 N" -> "120".
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _extract_number(text: str) -> float | None:
    if not text:
        return None
    matches = _NUMBER_RE.findall(text)
    if not matches:
        return None
    try:
        return float(matches[-1])
    except ValueError:  # pragma: no cover - regex guarantees a parseable form
        return None


def _normalize(text: str) -> str:
    """Lowercase and strip whitespace/symbols so equations match robustly.

    ``F = m·a`` and ``f=ma`` both normalise to ``f=ma``.
    """
    return "".join(ch for ch in text.lower() if not ch.isspace() and ch not in "·∗")


class EvaluatorAgent:
    """Deterministic rubric that scores learner answers and updates mastery."""

    def __init__(self, tolerance: float = 0.01) -> None:
        self.tolerance = tolerance

    # ── Core scoring ──

    def evaluate(
        self,
        learner_answer: str,
        *,
        expected: float | None = None,
        accept_terms: tuple[str, ...] = (),
        detected_misconception: MisconceptionType | None = None,
    ) -> Evaluation:
        """Score a learner's answer against a rubric and return an Evaluation.

        ``expected`` is the correct numeric answer (optional; exact-equation
        rubrics may omit it). ``accept_terms`` are phrases/symbols that indicate
        the learner invoked the right principle (e.g. ``"f=ma"``). A detected
        misconception dominates the result.
        """
        answer = (learner_answer or "").strip()
        if not answer:
            return self._result(EvaluationResult.INCOMPLETE, 0.0, "No answer given.")

        if detected_misconception is not None:
            return self._result(
                EvaluationResult.MISCONCEPTION_DETECTED,
                0.0,
                self._misconception_feedback(detected_misconception),
                detected_misconception=(detected_misconception,),
            )

        low = _normalize(answer)
        has_terms = any(_normalize(term) in low for term in accept_terms)
        number = _extract_number(answer)

        if expected is not None and number is not None and self._close(number, expected):
            return self._result(
                EvaluationResult.CORRECT,
                1.0,
                "Correct — the numeric answer matches. "
                + (
                    "You also used the right equation."
                    if has_terms
                    else "Now check the equation you used."
                ),
                correct_steps=("answer",) + (("equation",) if has_terms else ()),
                next_hint=None,
            )

        if number is not None and expected is not None and not self._close(number, expected):
            return self._result(
                EvaluationResult.INCORRECT,
                0.2,
                "The numeric answer is not right. Revisit the relationship between "
                "the quantities before recomputing.",
                incorrect_steps=("answer",),
                next_hint="Write the governing equation first, then substitute.",
            )

        if has_terms and (expected is None or number is None):
            return self._result(
                EvaluationResult.CORRECT if expected is None else EvaluationResult.PARTIAL,
                1.0 if expected is None else 0.6,
                "The right principle is in play."
                if expected is None
                else "Good — you have the equation. Now finish the numerical answer.",
                correct_steps=("equation",),
                next_hint="Substitute the given values and solve."
                if expected is not None
                else None,
            )

        # Reached here: no matching number and no recognized terms.
        return self._result(
            EvaluationResult.INCORRECT,
            0.1,
            "I can't see the governing equation or a numeric result yet. Try stating "
            "the relationship first.",
            next_hint="What connects force, mass and acceleration?",
        )

    # ── Learner-state application ──

    def apply(
        self,
        learner: LearnerState,
        evaluation: Evaluation,
        concept_id: str,
    ) -> LearnerState:
        """Fold an Evaluation into the learner's mastery and misconception records.

        Correct => mastery attempt is correct; otherwise an incorrect attempt.
        A MISCONCEPTION_DETECTED evaluation also ensures the misconception is
        recorded. Returns a new, immutable :class:`LearnerState`.
        """
        updated = learner.update_mastery(concept_id, evaluation.is_correct)
        for mis in evaluation.detected_misconceptions:
            updated = updated.record_misconception(concept_id, mis)
        return updated

    # ── Internals ──

    def _close(self, got: float, expected: float) -> bool:
        return abs(got - expected) <= self.tolerance * max(1.0, abs(expected))

    def _misconception_feedback(self, m: MisconceptionType) -> str:
        return (
            f"I see a common misconception here ({m.value}). Let's revisit it with a "
            "question rather than the answer."
        )

    def _result(
        self,
        result: EvaluationResult,
        score: float,
        feedback: str,
        *,
        detected_misconception: tuple[MisconceptionType, ...] = (),
        correct_steps: tuple[str, ...] = (),
        incorrect_steps: tuple[str, ...] = (),
        next_hint: str | None = None,
    ) -> Evaluation:
        return Evaluation(
            result=result,
            score=score,
            feedback=feedback,
            detected_misconceptions=detected_misconception,
            correct_steps=correct_steps,
            incorrect_steps=incorrect_steps,
            next_hint=next_hint,
            metadata={"evaluator": "rule_based_v1"},
        )


__all__ = ["EvaluatorAgent", "Evaluation", "EvaluationResult", "MisconceptionType"]
