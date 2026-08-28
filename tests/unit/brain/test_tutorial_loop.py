"""Tutorial-loop acceptance tests: simulated student vs. the Socratic professor.

This is the Phase 3 milestone: a scripted learner studies Newton's Second Law
and the professor scaffolds them (never revealing the answer), diagnoses a
misconception, and only advances mastery on correct attempts. Learner state is
checkpointed under the learner id (thread_id), so a lesson resumes across calls.

NOTE: sessions share a process-wide MemorySaver, so each test uses its own
learner id to keep checkpoints isolated.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.brain.professor import ProfessorAgent
from app.brain.tutorial import TutorialSession
from app.domain.learner import LearnerState, TutoringMode
from app.knowledge.lhs_adapter import LHSKnowledgeAdapter
from app.models.catalog import ProviderCatalog
from app.models.providers import MockProvider
from app.models.router import ModelRouter

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "lhs_knowledge_fixture.json"
FORCE = "lhs:phys.force"  # F = m·a; grounded; prereqs mass + acceleration

MASS = "lhs:phys.mass"
ACCEL = "lhs:phys.acceleration"
EXPECTED_FORCE = 120.0
ACCEPT_TERMS: tuple[str, ...] = ("f=m*a",)


def _professor(learner_id: str) -> ProfessorAgent:
    router = ModelRouter(ProviderCatalog([MockProvider(name="mock-tutor", model="m")]))
    knowledge = LHSKnowledgeAdapter(FIXTURE)
    return ProfessorAgent(router, knowledge, LearnerState(learner_id=learner_id))


def _grant_prereqs(session: TutorialSession) -> None:
    learner = session.learner.update_mastery(MASS, True)
    learner = learner.update_mastery(ACCEL, True)
    session.professor.learner = learner


@pytest.mark.asyncio
async def test_start_blocks_unmet_prerequisites() -> None:
    session = TutorialSession(_professor("blocked-1"))
    outcome = await session.start(FORCE, "blocked-1", TutoringMode.SOCRATIC_MENTOR)
    # Force requires mass + acceleration, which the student has not mastered.
    assert outcome["reason"] == "prerequisites_pending"
    assert outcome["ready"] == "false"


@pytest.mark.asyncio
async def test_simulated_student_full_lesson() -> None:
    session = TutorialSession(_professor("sim-1"))
    _grant_prereqs(session)

    outcome = await session.start(FORCE, "sim-1", TutoringMode.SOCRATIC_MENTOR)
    assert outcome["ready"] == "true"
    assert outcome["concept_id"] == FORCE

    # Turn 1: the student reveals a recognized misconception.
    t1 = await session.turn(
        "sim-1",
        "heavier objects fall faster",
        expected=EXPECTED_FORCE,
        accept_terms=ACCEPT_TERMS,
    )
    assert t1["detected_misconception"] == "heavier_falls_faster"
    # Evaluation dominates -> not correct; mastery not yet achieved.
    assert t1["evaluation_result"] != "correct"
    assert t1["mastered"] is False

    # Turn 2: the student gives the right principle but a numeric slip.
    t2 = await session.turn(
        "sim-1",
        "F = m * a, so it is 50 N",
        expected=EXPECTED_FORCE,
        accept_terms=ACCEPT_TERMS,
    )
    assert t2["detected_misconception"] is None
    # The professor's response is grounded on the canonical equation.
    assert t2["grounded"] is True
    assert t2["mastered"] is False

    # The student keeps correcting until the mastery model converges (>=0.85).
    result = None
    for _ in range(20):
        result = await session.turn(
            "sim-1",
            "F = m * a, the answer is 120 N",
            expected=EXPECTED_FORCE,
            accept_terms=ACCEPT_TERMS,
        )
        if result["mastered"]:
            break
    assert result is not None and result["mastered"] is True
    assert result["evaluation_result"] == "correct"

    # The learner's record persists across turns on the same session.
    mastery = result["learner"].get_mastery(FORCE)
    assert mastery is not None and mastery.correct_count >= 2


@pytest.mark.asyncio
async def test_checkpointed_state_resumes_across_sessions() -> None:
    """thread_id == learner_id means a new session picks up prior state."""
    session = TutorialSession(_professor("resume-1"))
    _grant_prereqs(session)
    await session.start(FORCE, "resume-1", TutoringMode.SOCRATIC_MENTOR)
    await session.turn("resume-1", "heavier objects fall faster")

    # A fresh facade (same thread) still sees the recorded misconception via
    # the checkpointed learner snapshot.
    fresh = TutorialSession(_professor("resume-1"))
    _grant_prereqs(fresh)
    await fresh.start(FORCE, "resume-1", TutoringMode.SOCRATIC_MENTOR)
    t = await fresh.turn("resume-1", "the answer is 120 N")

    learner = t["learner"]
    assert isinstance(learner, LearnerState)
    assert learner.learner_id == "resume-1"
    # The misconception recorded in the earlier session survives the resume.
    assert learner.get_misconception(FORCE) is not None
    # The prerequisite mastery recorded earlier also survives.
    assert learner.get_mastery(MASS) is not None
