"""ProfessorAgent — the Socratic tutoring brain.

Sits on top of the deterministic :mod:`app.brain.intents` pipeline and is the
cognitive engine's primary, domain-defining agent. It drives a one-on-one
tutoring dialogue by combining the pedagogical domain models
(:mod:`app.domain.learner`) with canonical knowledge from the
:class:`~app.knowledge.lhs_adapter.LHSKnowledgeAdapter` and the model pool
(:class:`~app.models.router.ModelRouter`).

Guiding invariants (from ARCHITECTURE-ESSENTIALS.md):

* **Grounded over generative** — when the target concept has a human-reviewed,
  canonical LearningHubSTEM definition we ground the Socratic scaffold in it and
  report ``grounded=True``. Otherwise the response is explicitly labeled
  ungrounded (``grounded=False``).
* **Prerequisite gating** — we will not present new material until the learner
  has mastered the concept's prerequisites.
* **No answer-reveal** — the professor scaffolds toward the answer (Socratic),
  it never hands the answer over.

Misconception diagnosis is rule-based (deterministic, fully testable) using the
existing :class:`MisconceptionType` catalog; prose generation goes through the
router so it works unchanged with the MockProvider in tests and a real provider
in production.
"""

from __future__ import annotations

import logging
from typing import Any

from app.domain.learner import (
    LearnerState,
    MisconceptionType,
    TutoringMode,
)
from app.knowledge.lhs_adapter import LHSKnowledgeAdapter
from app.models.providers import LLMMessage
from app.models.router import ModelRouter

logger = logging.getLogger(__name__)

# ── Misconception detection ────────────────────────────────────────────────
# Deterministic keyword signals mapped onto the canonical misconception catalog.
# Ordered so more specific multi-word phrases match first. Each signal is a
# lower-cased phrase that, when present in the learner's response, suggests the
# associated misconception. These are curated heuristics — they surface a
# hypothesis for the professor to probe, never a hard verdict alone.
_MISCONCEPTION_RULES: tuple[tuple[MisconceptionType, tuple[str, ...]], ...] = (
    (
        MisconceptionType.HEAVIER_FALLS_FASTER,
        (
            "heavier falls faster",
            "heavier objects fall faster",
            "heavier falls",
            "more mass falls faster",
            "heavier object falls",
        ),
    ),
    (
        MisconceptionType.ACTION_REACTION_CANCEL,
        (
            "forces cancel",
            "reaction force cancels",
            "action and reaction cancel",
            "equal and opposite cancel",
            "net force is zero because they cancel",
        ),
    ),
    (
        MisconceptionType.FORCE_VELOCITY_SAME_DIRECTION,
        (
            "force is always in the direction of motion",
            "force points in the direction it is moving",
            "force always points the way it moves",
            "force and motion are always in the same direction",
        ),
    ),
    (
        MisconceptionType.ACCELERATION_ALWAYS_SPEEDING_UP,
        (
            "acceleration always means speeding up",
            "acceleration is always speeding up",
            "acceleration always speeds things up",
            "acceleration means getting faster",
        ),
    ),
    (
        MisconceptionType.ZERO_VELOCITY_ZERO_ACCELERATION,
        (
            "zero velocity means zero acceleration",
            "no velocity no acceleration",
            "if it is not moving there is no acceleration",
            "stopped so no acceleration",
        ),
    ),
    (
        MisconceptionType.CONSTANT_SPEED_ZERO_ACCELERATION,
        (
            "constant speed means no acceleration",
            "constant speed zero acceleration",
            "moving at constant speed so acceleration is zero",
            "no acceleration because speed is constant",
        ),
    ),
)

# Socratic system prompts per mode. The professor scaffolds; it never reveals
# the canonical answer directly.
_MODE_PROMPTS: dict[TutoringMode, str] = {
    TutoringMode.SOCRATIC_MENTOR: (
        "You are PROFESSOR-J, a Socratic mentor. Guide the learner to the answer "
        "through targeted questions and scaffolding. Do not state the final answer "
        "yourself; lead them to it one step at a time."
    ),
    TutoringMode.EXPOSITORY_LECTURE: (
        "You are PROFESSOR-J. Give a clear, accurate, well-structured explanation "
        "of the concept grounded in its canonical definition. Use the provided "
        "definition and equation as the source of truth."
    ),
    TutoringMode.EXAM_DRILL: (
        "You are PROFESSOR-J. Pose a focused practice problem, then give terse, "
        "constructive feedback on the learner's attempt. Keep it exam-style."
    ),
    TutoringMode.RESEARCH_ADVISOR: (
        "You are PROFESSOR-J, a research advisor. Synthesize on-topic guidance and "
        "flag anything that is not grounded in the canonical source."
    ),
}

# Canonical equations/definitions are injected verbatim so a Socratic scaffold
# stays factually correct while the learner still does the reasoning.


class ProfessorAgent:
    """Rule-driven Socratic tutor backed by domain models + model router.

    State is carried in a :class:`LearnerState` (handed in on construction) so a
    session can be resumed across turns and, later, checkpoints.
    """

    def __init__(
        self,
        router: ModelRouter,
        knowledge: LHSKnowledgeAdapter,
        learner: LearnerState,
    ) -> None:
        self.router = router
        self.knowledge = knowledge
        self.learner = learner

    # ── Public session API ──

    async def open_concept(self, concept_id: str, mode: TutoringMode) -> LearnerState:
        """Begin (or switch) tutoring on a concept. Returns the new learner state.

        Gating: if the concept has prerequisites the learner has not mastered,
        the professor will not teach it yet (the caller can read
        :meth:`readiness_report` to surface the blocker).
        """
        self.learner = self.learner.set_active_concept(concept_id)
        self.learner = self.learner.set_mode(mode.value)
        return self.learner

    def readiness_report(self, concept_id: str) -> dict[str, Any]:
        """Describe whether the learner may start a concept and which blocker (if any)."""
        entity = self.knowledge.get_concept(concept_id)
        if entity is None:
            return {
                "ready": False,
                "concept_id": concept_id,
                "reason": "unknown_concept",
                "missing_prerequisites": [],
            }
        prereqs = self.knowledge.get_prerequisites(concept_id)
        missing = [
            p for p in prereqs if (m := self.learner.get_mastery(p)) is None or not m.is_mastered()
        ]
        return {
            "ready": len(missing) == 0,
            "concept_id": concept_id,
            "reason": "prerequisites_pending" if missing else "ready",
            "missing_prerequisites": missing,
        }

    async def socratic_turn(self, learner_prompt: str) -> dict[str, Any]:
        """Run one tutoring turn and return a rich result dict.

        Returns components the graph/brain layers need: the generated response,
        whether it is grounded, the detected misconception (if any), the updated
        learner state, and the provider that served the turn.
        """
        concept_id = self.learner.active_concept
        entity = self.knowledge.get_concept(concept_id) if concept_id else None
        grounded = bool(entity and entity.is_grounded())

        detected = self._detect_misconception(learner_prompt)
        if detected is not None:
            self.learner = self.learner.record_misconception(concept_id or "unknown", detected)

        prompt = self._build_socratic_prompt(learner_prompt, entity, grounded, detected)
        messages = [
            LLMMessage(role="system", content=prompt),
            LLMMessage(role="user", content=learner_prompt),
        ]
        result = await self.router.generate(messages)

        self.learner = self.learner.add_turn(self._turn_id())
        return {
            "response": result.text,
            "grounded": grounded,
            "detected_misconception": detected.value if detected else None,
            "learner": self.learner,
            "provider": result.provider,
            "concept_id": concept_id,
        }

    # ── Misconception diagnosis (deterministic) ──

    def detect_misconception(self, text: str) -> MisconceptionType | None:
        """Public alias for :meth:`_detect_misconception`.

        Returns the first catalog misconception whose signal phrase appears in
        ``text`` (case-insensitive), or ``None``.
        """
        return self._detect_misconception(text)

    def _detect_misconception(self, text: str) -> MisconceptionType | None:
        low = (text or "").lower().strip()
        if not low:
            return None
        for misconception, signals in _MISCONCEPTION_RULES:
            if any(signal in low for signal in signals):
                return misconception
        return None

    # ── Scaffold building ──

    def _build_socratic_prompt(
        self,
        learner_prompt: str,
        entity: Any | None,
        grounded: bool,
        detected: MisconceptionType | None,
    ) -> str:
        """Assemble the system prompt handed to the router for this turn."""
        am, bm = self._mode()
        system = _MODE_PROMPTS[am]

        context_parts: list[str] = []
        if entity is not None and grounded:
            if entity.definition:
                context_parts.append(f"Canonical definition: {entity.definition}")
            if entity.equation:
                context_parts.append(f"Canonical equation: {entity.equation}")
            if entity.name:
                context_parts.append(f"Concept: {entity.name}")
        else:
            context_parts.append(
                "[UNGROUNDED] No human-reviewed canonical source was found for this "
                "concept. Label any factual claims as ungrounded and recommend "
                "verifying independently."
            )

        if detected is not None:
            context_parts.append(
                f"The learner may hold the misconception '{detected.value}'. Without "
                "stating the answer, gently probe it with a question that exposes the "
                "tension."
            )

        return "\n".join(
            [
                system,
                f"Tutoring mode: {bm}.",
                "Mandate: never reveal the final answer directly; scaffold toward it.",
                *context_parts,
            ]
        )

    def _mode(self) -> tuple[TutoringMode, str]:
        try:
            mode = TutoringMode(self.learner.current_mode)
        except ValueError:  # pragma: no cover - defensive
            mode = TutoringMode.SOCRATIC_MENTOR
        return mode, mode.value

    def _turn_id(self) -> str:
        import uuid

        return f"turn-{uuid.uuid4().hex[:8]}"


__all__ = ["ProfessorAgent"]
