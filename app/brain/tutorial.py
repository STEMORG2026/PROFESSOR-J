"""Tutorial path — ProfessorAgent + EvaluatorAgent orchestrated in a checkpointer graph.

This is the sessionful face of the cognitive engine: a checkpointed LangGraph
loop (``tutorial``) that runs one full teaching turn per invocation. Learner
state is serialised into the graph state and checkpointed under
``thread_id == learner/session id`` via a :class:`MemorySaver`, so a Socratic
lesson resumes across calls — and, later, across processes via a durable
checkpointer (Phase 4 SEAM: ``MemorySaver <-> Postgres``).

The generic :mod:`app.brain.graph` pipeline stays untouched; this module layers
the tutoring loop on top and is referenced by callers once a prompt classifies
as :attr:`Intent.TUTORIAL`.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.brain.evaluator import EvaluatorAgent
from app.brain.professor import ProfessorAgent
from app.domain.learner import (
    LearnerState,
    MasteryScore,
    MisconceptionState,
    MisconceptionType,
    TutoringMode,
)

logger = logging.getLogger(__name__)


class TutorialState(TypedDict, total=False):
    """Per-turn state for the tutoring loop (JSON-safe, checkpointed)."""

    prompt: str
    concept_id: str
    learner_snapshot: dict[str, Any]
    response: str
    provider: str
    grounded: bool
    detected_misconception: str | None
    evaluation_result: str | None
    mastered: bool
    # Controller-supplied rubric; carried in state so it survives checkpointing.
    expected: float | None
    accept_terms: tuple[str, ...]


# ── LearnerState <-> JSON snapshot ──────────────────────────────────────────


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def _misconception_to_dict(m: MisconceptionState) -> dict[str, Any]:
    """Serialise a MisconceptionState, storing its enum as a plain string."""
    return {
        "learner_id": m.learner_id,
        "concept_id": m.concept_id,
        "misconception": m.misconception.value,
        "resolved": m.resolved,
        "detected_at": _iso(m.detected_at),
        "occurrences": m.occurrences,
        "resolved_at": _iso(m.resolved_at),
        "resolution_method": m.resolution_method,
    }


def learner_to_snapshot(learner: LearnerState) -> dict[str, Any]:
    """Serialise a LearnerState into a JSON-safe dict (for checkpointing).

    Enum members are stored as plain strings so the snapshot round-trips through
    LangGraph's checkpointer without needing a registered msgpack type.
    """
    return {
        "learner_id": learner.learner_id,
        "mastery": {
            cid: {
                "concept_id": score.concept_id,
                "score": score.score,
                "confidence": score.confidence,
                "practice_count": score.practice_count,
                "correct_count": score.correct_count,
                "last_practiced": _iso(score.last_practiced),
                "updated_at": _iso(score.updated_at),
            }
            for cid, score in learner.mastery.items()
        },
        "misconceptions": {
            cid: _misconception_to_dict(m) for cid, m in learner.misconceptions.items()
        },
        "dialogue_history": list(learner.dialogue_history),
        "current_mode": learner.current_mode,
        "active_concept": learner.active_concept,
        "created_at": _iso(learner.created_at),
        "updated_at": _iso(learner.updated_at),
    }


def learner_from_snapshot(snapshot: dict[str, Any], learner_id: str) -> LearnerState:
    """Rebuild a LearnerState from its snapshot (graceful vs. older data)."""
    mastery: dict[str, MasteryScore] = {}
    for cid, raw in (snapshot.get("mastery") or {}).items():
        mastery[cid] = MasteryScore(
            concept_id=raw.get("concept_id", cid),
            score=float(raw.get("score", 0.0)),
            confidence=float(raw.get("confidence", 1.0)),
            practice_count=int(raw.get("practice_count", 0)),
            correct_count=int(raw.get("correct_count", 0)),
        )
    misconceptions: dict[str, MisconceptionState] = {}
    for cid, raw in (snapshot.get("misconceptions") or {}).items():
        try:
            misconception = MisconceptionType(raw.get("misconception", ""))
        except ValueError:
            misconception = MisconceptionType.CORRELATION_IMPLIES_CAUSATION
        misconceptions[cid] = MisconceptionState(
            learner_id=raw.get("learner_id", learner_id),
            concept_id=raw.get("concept_id", cid),
            misconception=misconception,
            resolved=bool(raw.get("resolved", False)),
            occurrences=int(raw.get("occurrences", 1)),
        )
    return LearnerState(
        learner_id=learner_id,
        mastery=mastery,
        misconceptions=misconceptions,
        dialogue_history=tuple(snapshot.get("dialogue_history") or ()),
        current_mode=snapshot.get("current_mode", "socratic_mentor"),
        active_concept=snapshot.get("active_concept"),
    )


# ── Graph composition ───────────────────────────────────────────────────────


def _make_tutorial_node(professor: ProfessorAgent, evaluator: EvaluatorAgent) -> Any:
    """Return a LangGraph node running one full tutoring turn.

    The node: restores learner continuity from the checkpointed snapshot, runs
    the professor turn, grades + applies the evaluator result, and persists the
    updated learner back into state.
    """

    async def _node(state: TutorialState) -> dict[str, Any]:
        concept_id = state.get("concept_id", "")
        prompt = state.get("prompt", "")

        snapshot = state.get("learner_snapshot")
        if snapshot:
            professor.learner = learner_from_snapshot(snapshot, professor.learner.learner_id)

        result = await professor.socratic_turn(prompt)
        detected = professor.detect_misconception(prompt)

        # Controller-supplied rubric wins; otherwise fall back to the concept's
        # canonical equation as the accepted-principle signal.
        accept_terms = state.get("accept_terms") or ()
        expected = state.get("expected")
        if not accept_terms and concept_id:
            entity = professor.knowledge.get_concept(concept_id)
            if entity and entity.equation:
                accept_terms = (entity.equation,)

        evaluation = evaluator.evaluate(
            prompt,
            expected=expected,
            accept_terms=accept_terms,
            detected_misconception=detected,
        )
        learner = evaluator.apply(professor.learner, evaluation, concept_id)
        professor.learner = learner

        mastery = learner.get_mastery(concept_id)
        return {
            "response": result["response"],
            "provider": result["provider"],
            "grounded": bool(result["grounded"]),
            "detected_misconception": result["detected_misconception"],
            "evaluation_result": evaluation.result.value,
            "learner_snapshot": learner_to_snapshot(learner),
            "mastered": bool(mastery is not None and mastery.is_mastered()),
        }

    return _node


def build_tutorial_graph(
    professor: ProfessorAgent,
    evaluator: EvaluatorAgent,
    checkpointer: Any | None = None,
) -> Any:
    """Compile the tutoring loop graph, checkpointed by default (MemorySaver).

    ``checkpointer`` may be swapped for a Postgres checkpointer (Phase 4 SEAM);
    a process-shared MemorySaver is used when none is supplied. See
    :data:`_DEFAULT_CHECKPOINTER`.
    """
    graph = StateGraph(TutorialState)
    graph.add_node("tutorial", _make_tutorial_node(professor, evaluator))
    graph.add_edge(START, "tutorial")
    graph.add_edge("tutorial", END)
    return graph.compile(checkpointer=checkpointer or _DEFAULT_CHECKPOINTER)


# A process-shared MemorySaver makes every TutorialSession in the process share
# checkpoint state keyed by thread_id, so a learner can resume across separate
# session facades. Swap for a Postgres checkpointer in Phase 4 for durability
# across processes.
_DEFAULT_CHECKPOINTER = MemorySaver()


class TutorialSession:
    """Sessionful facade over the checkpointed tutoring graph.

    Drive a Socratic lesson on a concept; learner state is checkpointed under
    ``thread_id = learner_id`` so a session resumes across calls — including
    across separate :class:`TutorialSession` instances in the same process
    (they share the default checkpointer).
    """

    def __init__(
        self,
        professor: ProfessorAgent,
        evaluator: EvaluatorAgent | None = None,
    ) -> None:
        self.professor = professor
        self.evaluator = evaluator or EvaluatorAgent()
        self.graph = build_tutorial_graph(professor, self.evaluator)

    @property
    def learner(self) -> LearnerState:
        return self.professor.learner

    async def start(
        self,
        concept_id: str,
        learner_id: str,
        mode: TutoringMode = TutoringMode.SOCRATIC_MENTOR,
    ) -> dict[str, str]:
        """Open a concept in a mode; return the readiness report + first prompt."""
        report = self.professor.readiness_report(concept_id)
        entity = self.professor.knowledge.get_concept(concept_id)
        if entity is None:
            return {
                "concept_id": concept_id,
                "mode": mode.value,
                "problem": "",
                "ready": "false",
                "reason": "unknown_concept",
            }
        await self.professor.open_concept(concept_id, mode)
        problem = (
            f"You are now studying '{entity.name}'. "
            "Explain in your own words the relationship it describes."
        )
        return {
            "concept_id": concept_id,
            "mode": mode.value,
            "problem": problem,
            "ready": str(report["ready"]).lower(),
            "reason": report["reason"],
        }

    async def turn(
        self,
        learner_id: str,
        learner_attempt: str,
        *,
        expected: float | None = None,
        accept_terms: tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        """Run one tutoring turn for a learner's attempt and return the outcome.

        ``expected`` (correct numeric answer) and ``accept_terms`` (accepted
        principle/equation phrases) form the evaluation rubric. When omitted the
        concept's canonical equation is the acceptance signal.
        """
        concept_id = self.professor.learner.active_concept or ""
        out = await self.graph.ainvoke(
            {
                "concept_id": concept_id,
                "prompt": learner_attempt,
                "expected": expected,
                "accept_terms": accept_terms or (),
            },
            config={"configurable": {"thread_id": learner_id}},
        )
        return {
            "response": out.get("response", ""),
            "provider": out.get("provider", ""),
            "grounded": bool(out.get("grounded")),
            "detected_misconception": out.get("detected_misconception"),
            "evaluation_result": out.get("evaluation_result"),
            "mastered": bool(out.get("mastered")),
            "learner": self.professor.learner,
        }


__all__ = [
    "TutorialSession",
    "TutorialState",
    "build_tutorial_graph",
    "learner_to_snapshot",
    "learner_from_snapshot",
    "EvaluatorAgent",
    "ProfessorAgent",
]
