import pytest
from pathlib import Path
import json
from typing import Any

from app.skills.base import Skill, SkillMetadata, SkillResult, SkillStatus
from app.skills.registry import SkillRegistry, get_skill_registry, reset_skill_registry


class DummySkill(Skill[str]):
    def _default_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="dummy_skill",
            description="A dummy skill for testing",
            category="test",
        )

    async def execute(self, **kwargs: Any) -> SkillResult[str]:
        return SkillResult.success("Success!")


@pytest.fixture
def registry(tmp_path: Path) -> SkillRegistry:
    return SkillRegistry(skills_dir=tmp_path)


@pytest.fixture
def dummy_skill() -> DummySkill:
    return DummySkill()


def test_registry_initialization(tmp_path: Path) -> None:
    reg = SkillRegistry(skills_dir=tmp_path)
    assert reg._skills_dir == tmp_path
    assert tmp_path.exists()


def test_register_and_get_skill(registry: SkillRegistry, dummy_skill: DummySkill) -> None:
    registry.register(dummy_skill)
    retrieved = registry.get("dummy_skill")
    assert retrieved is dummy_skill

    metadata = registry.get_metadata("dummy_skill")
    assert metadata is not None
    assert metadata.name == "dummy_skill"


def test_unregister_skill(registry: SkillRegistry, dummy_skill: DummySkill) -> None:
    registry.register(dummy_skill)
    assert registry.unregister("dummy_skill") is True
    assert registry.get("dummy_skill") is None
    assert registry.get_metadata("dummy_skill") is None
    assert registry.unregister("non_existent_skill") is False


def test_list_skills_and_categories(registry: SkillRegistry, dummy_skill: DummySkill) -> None:
    registry.register(dummy_skill)

    skills = registry.list_skills()
    assert len(skills) == 1
    assert skills[0].name == "dummy_skill"

    cat_skills = registry.list_skills(category="test")
    assert len(cat_skills) == 1

    wrong_cat = registry.list_skills(category="other")
    assert len(wrong_cat) == 0

    categories = registry.get_categories()
    assert categories == ["test"]


def test_get_all_schemas(registry: SkillRegistry, dummy_skill: DummySkill) -> None:
    registry.register(dummy_skill)
    schemas = registry.get_all_schemas()
    assert len(schemas) == 1
    assert schemas[0]["name"] == "dummy_skill"
    assert "parameters" in schemas[0]
    assert "returns" in schemas[0]


@pytest.mark.asyncio
async def test_execute_skill(registry: SkillRegistry, dummy_skill: DummySkill) -> None:
    registry.register(dummy_skill)

    result = await registry.execute("dummy_skill")
    assert result.status == SkillStatus.SUCCESS
    assert result.data == "Success!"

    missing_result = await registry.execute("missing_skill")
    assert missing_result.status == SkillStatus.FAILED
    assert missing_result.error is not None
    assert "not found" in missing_result.error


def test_save_and_load_from_disk(
    registry: SkillRegistry, dummy_skill: DummySkill, tmp_path: Path
) -> None:
    registry.register(dummy_skill)

    # Test saving
    assert registry.save_to_disk("dummy_skill") is True

    skill_file = tmp_path / "dummy_skill.json"
    assert skill_file.exists()

    with open(skill_file) as f:
        data = json.load(f)
        assert data["metadata"]["name"] == "dummy_skill"

    # Test loading
    new_registry = SkillRegistry(skills_dir=tmp_path)
    loaded_skill = new_registry.load_from_disk("dummy_skill", DummySkill)

    assert loaded_skill is not None
    assert loaded_skill.metadata.name == "dummy_skill"
    assert new_registry.get("dummy_skill") is not None


def test_load_all_from_disk(
    registry: SkillRegistry, dummy_skill: DummySkill, tmp_path: Path
) -> None:
    registry.register(dummy_skill)
    registry.save_to_disk("dummy_skill")

    new_registry = SkillRegistry(skills_dir=tmp_path)
    count = new_registry.load_all_from_disk({"dummy_skill": DummySkill})

    assert count == 1
    assert new_registry.get("dummy_skill") is not None


def test_global_registry(tmp_path: Path) -> None:
    reset_skill_registry()

    reg1 = get_skill_registry(tmp_path)
    reg2 = get_skill_registry()

    assert reg1 is reg2
    reset_skill_registry()
