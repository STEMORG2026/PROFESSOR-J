"""Tests for built-in skills (registry wiring, grounding, honest unimplemented signals)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.skills.base import Skill
from app.skills.builtin import (
    BUILTIN_SKILLS,
    CodeExecutionSkill,
    FilesystemSkill,
    LHSTEMSkill,
    MemorySkill,
    WebSearchSkill,
    create_builtin_skills,
)
from app.skills.registry import SkillRegistry

FIXTURE = (
    Path(__file__).resolve().parents[2] / "fixtures" / "lhs_knowledge_fixture.json"
)


@pytest.fixture
def registry() -> SkillRegistry:
    return SkillRegistry(skills_dir=FIXTURE.parent / "tmp_skills")


def test_create_builtin_skills_registers_all() -> None:
    skills = create_builtin_skills()
    assert set(skills) == set(BUILTIN_SKILLS)


def test_register_builtin_skills_registers_six(registry: SkillRegistry) -> None:
    from app.skills.builtin import register_builtin_skills

    count = register_builtin_skills(registry)
    assert count == 6
    assert registry.get("filesystem") is not None
    assert registry.get("lhstem_knowledge") is not None
    assert registry.get("memory") is not None


class TestLHSTEMSkill:
    @pytest.fixture
    def skill(self, monkeypatch: pytest.MonkeyPatch) -> LHSTEMSkill:
        from app.knowledge.lhs_adapter import LHSKnowledgeAdapter

        adapter = LHSKnowledgeAdapter(FIXTURE)
        s = LHSTEMSkill()
        monkeypatch.setattr(s, "_get_adapter", lambda: adapter)
        return s

    async def test_get_concept_grounded(self, skill: LHSTEMSkill) -> None:
        result = await skill(operation="get_concept", entity_id="lhs:phys.force")
        assert result.status.value == "success"
        assert result.data is not None
        assert result.data["concept"]["id"] == "lhs:phys.force"
        assert result.data["grounded"] is True

    async def test_get_concept_not_found(self, skill: LHSTEMSkill) -> None:
        result = await skill(operation="get_concept", entity_id="lhs:nope")
        assert result.status.value == "failed"
        assert "not found" in (result.error or "")

    async def test_has_concept(self, skill: LHSTEMSkill) -> None:
        result = await skill(operation="has_concept", entity_id="lhs:phys.force")
        assert result.status.value == "success"
        assert result.data is not None
        assert result.data["has_concept"] is True

    async def test_prerequisites(self, skill: LHSTEMSkill) -> None:
        result = await skill(operation="get_prerequisites", entity_id="lhs:phys.force")
        assert result.status.value == "success"
        assert result.data is not None
        assert "lhs:phys.mass" in result.data["prerequisites"]

    async def test_search(self, skill: LHSTEMSkill) -> None:
        result = await skill(operation="search", query="force")
        assert result.status.value == "success"
        assert result.data is not None
        assert any("force" in r["name"].lower() for r in result.data["results"])

    async def test_unknown_operation_fails(self, skill: LHSTEMSkill) -> None:
        result = await skill(operation="nope")
        assert result.status.value == "failed"


class TestNotImplementedSkills:
    """Unimplemented capabilities must fail loudly, never silently succeed."""

    @pytest.mark.parametrize(
        "skill_cls,op",
        [
            (WebSearchSkill, {}),
            (CodeExecutionSkill, {}),
            # Memory validates params first; supply a valid operation to reach execute().
            (MemorySkill, {"operation": "store"}),
        ],
    )
    async def test_returns_failure_not_success(
        self, skill_cls: type[Skill[Any]], op: dict[str, Any]
    ) -> None:
        skill = skill_cls()
        result = await skill(**op)
        assert result.status.value == "failed"
        assert result.data is None
        assert result.metadata.get("not_implemented") is True
        assert "not implemented" in (result.error or "")


class TestFilesystemSkill:
    async def test_write_read_roundtrip(self, tmp_path: Path) -> None:
        skill = FilesystemSkill()
        target = tmp_path / "hello.txt"
        w = await skill(operation="write", path=str(target), content="hi")
        assert w.status.value == "success"
        r = await skill(operation="read", path=str(target))
        assert r.status.value == "success"
        assert r.data is not None
        assert r.data["content"] == "hi"

    async def test_read_missing_fails(self, tmp_path: Path) -> None:
        skill = FilesystemSkill()
        r = await skill(operation="read", path=str(tmp_path / "missing.txt"))
        assert r.status.value == "failed"
