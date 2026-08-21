"""Skill Registry — Central registry for skill discovery, loading, and persistence."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.skills.base import Skill, SkillMetadata, SkillResult

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Central registry for skill discovery and management."""

    def __init__(self, skills_dir: Path | None = None) -> None:
        self._skills: dict[str, Skill] = {}
        self._metadata: dict[str, SkillMetadata] = {}
        self._skills_dir = skills_dir or Path("data/skills")
        self._skills_dir.mkdir(parents=True, exist_ok=True)

    def register(self, skill: Skill) -> None:
        """Register a skill instance."""
        name = skill.metadata.name
        if name in self._skills:
            logger.warning("Overwriting existing skill: %s", name)
        self._skills[name] = skill
        self._metadata[name] = skill.metadata
        logger.info("Registered skill: %s (%s)", name, skill.metadata.category)

    def unregister(self, name: str) -> bool:
        """Unregister a skill."""
        if name in self._skills:
            del self._skills[name]
            del self._metadata[name]
            logger.info("Unregistered skill: %s", name)
            return True
        return False

    def get(self, name: str) -> Skill | None:
        """Get a skill by name."""
        return self._skills.get(name)

    def get_metadata(self, name: str) -> SkillMetadata | None:
        """Get skill metadata by name."""
        return self._metadata.get(name)

    def list_skills(
        self,
        category: str | None = None,
        tag: str | None = None,
    ) -> list[SkillMetadata]:
        """List all registered skills, optionally filtered."""
        skills = list(self._metadata.values())
        if category:
            skills = [s for s in skills if s.category == category]
        if tag:
            skills = [s for s in skills if tag in s.tags]
        return skills

    def get_categories(self) -> list[str]:
        """Get all unique skill categories."""
        return sorted({m.category for m in self._metadata.values()})

    def get_all_schemas(self) -> list[dict[str, Any]]:
        """Get all skill schemas for LLM function calling."""
        return [skill.get_schema() for skill in self._skills.values()]

    async def execute(
        self,
        name: str,
        **kwargs: Any,
    ) -> SkillResult:
        """Execute a skill by name."""
        skill = self._skills.get(name)
        if not skill:
            return SkillResult.failure(f"Skill not found: {name}")
        return await skill(**kwargs)

    def save_to_disk(self, skill_name: str) -> bool:
        """Persist a skill's metadata to disk."""
        skill = self._skills.get(skill_name)
        if not skill:
            return False

        skill_file = self._skills_dir / f"{skill_name}.json"
        try:
            data = {
                "metadata": skill.metadata.to_dict(),
                "registered_at": datetime.utcnow().isoformat() + "Z",
            }
            skill_file.write_text(json.dumps(data, indent=2))
            return True
        except Exception as e:
            logger.error("Failed to save skill %s: %s", skill_name, e)
            return False

    def load_from_disk(self, skill_name: str, skill_class: type[Skill]) -> Skill | None:
        """Load a skill from disk metadata and instantiate it."""
        skill_file = self._skills_dir / f"{skill_name}.json"
        if not skill_file.exists():
            return None

        try:
            data = json.loads(skill_file.read_text())
            metadata_dict = data.get("metadata", {})
            metadata = SkillMetadata(**metadata_dict)
            skill = skill_class(metadata=metadata)
            self.register(skill)
            return skill
        except Exception as e:
            logger.error("Failed to load skill %s: %s", skill_name, e)
            return None

    def load_all_from_disk(self, skill_classes: dict[str, type[Skill]]) -> int:
        """Load all skills from disk using provided class mapping."""
        loaded = 0
        for skill_file in self._skills_dir.glob("*.json"):
            skill_name = skill_file.stem
            if skill_name in skill_classes:
                if self.load_from_disk(skill_name, skill_classes[skill_name]):
                    loaded += 1
        return loaded


# Global registry instance
_registry: SkillRegistry | None = None


def get_skill_registry(skills_dir: Path | None = None) -> SkillRegistry:
    """Get or create the global skill registry."""
    global _registry
    if _registry is None:
        _registry = SkillRegistry(skills_dir)
    return _registry


def reset_skill_registry() -> None:
    """Reset the global registry (for testing)."""
    global _registry
    _registry = None


from datetime import datetime
