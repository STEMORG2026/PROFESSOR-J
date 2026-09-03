"""PROFESSOR-J Skill System — Reusable agent capabilities with persistence."""

from __future__ import annotations

from app.skills.base import Skill, SkillError, SkillMetadata, SkillResult
from app.skills.builtin import (
    ArxivSkill,
    CodeExecutionSkill,
    FilesystemSkill,
    GitExtendedSkill,
    GitHubAuthSkill,
    GitHubCodeReviewSkill,
    GitHubPRWorkflowSkill,
    GitSkill,
    GroundedCitationsSkill,
    LHSTEMSkill,
    MCPSkill,
    MemorySkill,
    ProjectBuildSkill,
    WebSearchSkill,
    WorkspaceSynthesisSkill,
    create_builtin_skills,
    register_builtin_skills,
)
from app.skills.registry import SkillRegistry, get_skill_registry

__all__ = [
    "SkillRegistry",
    "get_skill_registry",
    "Skill",
    "SkillMetadata",
    "SkillResult",
    "SkillError",
    "FilesystemSkill",
    "GitSkill",
    "WebSearchSkill",
    "CodeExecutionSkill",
    "LHSTEMSkill",
    "MemorySkill",
    "ProjectBuildSkill",
    "GitExtendedSkill",
    "FileTemplateSkill",
    "MCPSkill",
    "GroundedCitationsSkill",
    "ArxivSkill",
    "WorkspaceSynthesisSkill",
    "GitHubAuthSkill",
    "GitHubCodeReviewSkill",
    "GitHubPRWorkflowSkill",
    "create_builtin_skills",
    "register_builtin_skills",
]
