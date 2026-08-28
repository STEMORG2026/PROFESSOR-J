"""Tests for ProfessorAgent — misconception diagnosis, grounding, gating."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.brain.professor import ProfessorAgent
from app.domain.learner import LearnerState, MisconceptionType, TutoringMode
from app.knowledge.lhs_adapter import LHSKnowledgeAdapter
from app.models.catalog import ProviderCatalog
from app.models.providers import MockProvider
from app.models.router import ModelRouter

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "lhs_knowledge_fixture.json"

FORCE = "lhs:phys.force"  # grounded, equation F = m·a, prereqs mass + acceleration


def _agent() -> tuple[ProfessorAgent, LHSKnowledgeAdapter, ModelRouter]:
    router = ModelRouter(ProviderCatalog([MockProvider(name="mock-prof", model="m")]))
    knowledge = LHSKnowledgeAdapter(FIXTURE)
    learner = LearnerState(learner_id="stu-1")
    return ProfessorAgent(router, knowledge, learner), knowledge, router


class TestMisconceptionDetection:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("heavier objects fall faster", MisconceptionType.HEAVIER_FALLS_FASTER),
            (
                "force is always in the direction of motion",
                MisconceptionType.FORCE_VELOCITY_SAME_DIRECTION,
            ),
            (
                "acceleration always means speeding up",
                MisconceptionType.ACCELERATION_ALWAYS_SPEEDING_UP,
            ),
            (
                "zero velocity means zero acceleration",
                MisconceptionType.ZERO_VELOCITY_ZERO_ACCELERATION,
            ),
        ],
    )
    def test_detects_catalog_misconception(self, text: str, expected: MisconceptionType) -> None:
        agent, _, _ = _agent()
        assert agent.detect_misconception(text) == expected

    def test_no_misconception_for_benign_answer(self) -> None:
        agent, _, _ = _agent()
        assert agent.detect_misconception("F = m times a, so force equals 120 N") is None

    def test_empty_text(self) -> None:
        agent, _, _ = _agent()
        assert agent.detect_misconception("") is None


class TestReadinessGating:
    def test_blocks_when_prerequisites_unmet(self) -> None:
        agent, _, _ = _agent()
        report = agent.readiness_report(FORCE)
        assert report["ready"] is False
        assert report["reason"] == "prerequisites_pending"
        assert set(report["missing_prerequisites"]) == {
            "lhs:phys.mass",
            "lhs:phys.acceleration",
        }

    def test_ready_once_prerequisites_mastered(self) -> None:
        agent, _, _ = _agent()
        learner = agent.learner.update_mastery("lhs:phys.mass", True)
        learner = learner.update_mastery("lhs:phys.acceleration", True)
        agent.learner = learner
        report = agent.readiness_report(FORCE)
        assert report["ready"] is True
        assert report["reason"] == "ready"

    def test_unknown_concept(self) -> None:
        agent, _, _ = _agent()
        report = agent.readiness_report("lhs:does.not.exist")
        assert report["ready"] is False
        assert report["reason"] == "unknown_concept"


class TestGroundedness:
    @pytest.mark.asyncio
    async def test_grounded_concept(self) -> None:
        agent, _, _ = _agent()
        await agent.open_concept(FORCE, TutoringMode.SOCRATIC_MENTOR)
        out = await agent.socratic_turn("I think force is mass times acceleration")
        assert out["grounded"] is True

    @pytest.mark.asyncio
    async def test_ungrounded_concept(self) -> None:
        # balanced-equation is DRAFT and AI-drafted -> ungrounded
        agent, _, _ = _agent()
        await agent.open_concept("lhs:chem.balanced-equation", TutoringMode.SOCRATIC_MENTOR)
        out = await agent.socratic_turn("What is a balanced equation?")
        assert out["grounded"] is False

    @pytest.mark.asyncio
    async def test_assertion_never_reveals_answer_in_scaffold(self) -> None:
        # The Socratic system prompt must mandate scaffolding, not hand the answer.
        agent, knowledge, _ = _agent()
        await agent.open_concept(FORCE, TutoringMode.SOCRATIC_MENTOR)
        entity = knowledge.get_concept(FORCE)
        prompt = agent._build_socratic_prompt(
            "force equals mass times acceleration",
            entity,
            grounded=True,
            detected=None,
        )
        assert "never reveal the final answer directly" in prompt
        # Canonical grounding material is injected so the scaffold stays accurate.
        assert "F = m·a" in prompt

    @pytest.mark.asyncio
    async def test_turn_records_misconception(self) -> None:
        agent, _, _ = _agent()
        await agent.open_concept(FORCE, TutoringMode.SOCRATIC_MENTOR)
        out = await agent.socratic_turn("heavier objects fall faster")
        assert out["detected_misconception"] == (MisconceptionType.HEAVIER_FALLS_FASTER.value)
        assert agent.learner.get_misconception(FORCE) is not None
