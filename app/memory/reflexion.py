"""ReflexionEngine — turn-level self-improvement over outcomes (Phase 4).

After a tutoring/completion turn, the engine reflects on the outcome and
produces durable lessons: what worked, what to avoid, and which learner memory
knot to reinforce. Lessons are stored through the same
:class:`~app.memory.manager.MemoryManager` / :class:`~app.memory.schema.Memory`
path the rest of memory uses, so they are retrievable by the hybrid ranker —
the self-improvement loop JARVIS's Reflexion provided.

The reflection is deterministic and rule-based now (no LLM), so it is fully
testable; an LLM-grounded reflection over a transcript is a later increment.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.domain.learner import EvaluationResult
from app.memory.manager import MemoryManager

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Reflection:
    """A deterministic lesson distilled from a turn outcome."""

    learner_id: str
    concept_id: str
    kind: str  # reinforcement | correction | misconception
    summary: str
    action: str


class ReflexionEngine:
    """Distill outcomes into durable learner lessons and store them."""

    def __init__(self, manager: MemoryManager) -> None:
        self._manager = manager

    def reflect(
        self,
        learner_id: str,
        concept_id: str,
        evaluation_result: str | EvaluationResult,
        *,
        detected_misconception: str | None = None,
    ) -> Reflection:
        """Produce a lesson for a turn outcome and persist it to memory."""
        result = (
            evaluation_result.value
            if isinstance(evaluation_result, EvaluationResult)
            else evaluation_result
        )
        if detected_misconception:
            reflection = Reflection(
                learner_id=learner_id,
                concept_id=concept_id,
                kind="misconception",
                summary=f"Learner showed misconception '{detected_misconception}' on {concept_id}.",
                action="Probe this misconception Socratic-style next session.",
            )
        elif result == EvaluationResult.CORRECT.value:
            reflection = Reflection(
                learner_id=learner_id,
                concept_id=concept_id,
                kind="reinforcement",
                summary=f"Learner mastered {concept_id} (correct attempt).",
                action="Reinforce and move to next prerequisite.",
            )
        else:
            reflection = Reflection(
                learner_id=learner_id,
                concept_id=concept_id,
                kind="correction",
                summary=f"Learner erred on {concept_id} ({result}).",
                action="Re-teach with scaffolding before advancing.",
            )
        self._manager.store(
            {
                "category": "reflexion",
                "type": reflection.kind,
                "value": reflection.summary,
                "behavior": "append",
                "metadata": {
                    "scope": "reflexion",
                    "learner_id": learner_id,
                    "concept_id": concept_id,
                    "kind": reflection.kind,
                    "action": reflection.action,
                },
            }
        )
        return reflection

    def lessons(self, learner_id: str, k: int = 5) -> list[dict[str, Any]]:
        """Retrieve recent durable lessons for a learner."""
        out: list[dict[str, Any]] = []
        for memory in self._manager.get_all():
            meta = memory.metadata or {}
            if meta.get("scope") != "reflexion" or meta.get("learner_id") != learner_id:
                continue
            out.append(
                {
                    "kind": meta.get("kind"),
                    "action": meta.get("action"),
                    "summary": memory.value,
                }
            )
        return out[:k]


__all__ = ["ReflexionEngine", "Reflection"]
