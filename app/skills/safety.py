"""Skill risk classification — the tier a skill executes under.

Created in response to audit findings S0-3 and S1-23. Two defects motivated it:

1. ``POST /api/skills/execute`` called skills directly, so no safety tier was consulted
   and ``ToolExecutor`` was never involved.
2. ``Skill.requires_approval`` was declared by two skills and **read by nothing**
   (``app/skills/base.py`` never consults it), so it read as a control and enforced
   nothing.

Every name below was checked against the live registry produced by
``register_builtin_skills`` (15 skills as of this revision). A skill that is not named here
is treated as ``DESTRUCTIVE`` — the fail-closed default, so adding a new skill without
classifying it cannot silently expose it.

The classification is a judgement call, not a derivation, and should be reviewed by the
owner rather than trusted because it exists.
"""

from __future__ import annotations

from app.domain.tool import SafetyTier
from app.skills.base import Skill

#: Skills that only read, compute, or fetch public data. These auto-approve.
#: `arxiv` performs a live outbound read against a public API; `grounded_citations` and
#: `lhstem_knowledge` are read-only with respect to local state.
_SAFE_SKILLS: frozenset[str] = frozenset(
    {
        "arxiv",
        "grounded_citations",
        "lhstem_knowledge",
    }
)

#: Skills with side effects that are recoverable and workspace-scoped. These auto-approve
#: under the default policy but are logged.
_SENSITIVE_SKILLS: frozenset[str] = frozenset(
    {
        "project_build",
        "workspace_synthesis",
    }
)

#: Skills that write, delete, execute subprocesses, mutate remotes, or handle credentials.
#: These require an explicit human approval callback, which is absent in the current
#: deployment — so they are refused rather than executed. That is the intended containment
#: behaviour after the audit confirmed an unauthenticated `filesystem delete` succeeded.
_DESTRUCTIVE_SKILLS: frozenset[str] = frozenset(
    {
        "code_execution",
        "file_template",
        "filesystem",
        "git",
        "git_extended",
        "github_auth",
        "github_code_review",
        "github_pr_workflow",
        "memory",
        "web_search",
    }
)

#: Registered skills intentionally left to the fail-closed default, mapped to the reason.
#: Kept explicit so the coverage test can distinguish "deliberate" from "forgotten".
_DELIBERATELY_UNCLASSIFIED: dict[str, str] = {}


def tier_for_skill(skill: Skill[object]) -> SafetyTier:
    """Return the safety tier for ``skill``.

    An explicit classification wins; otherwise the skill is treated as ``DESTRUCTIVE``.
    """
    name = skill.metadata.name
    if name in _SAFE_SKILLS:
        return SafetyTier.SAFE
    if name in _SENSITIVE_SKILLS:
        return SafetyTier.SENSITIVE
    # Classified destructive, or unclassified -- both require approval.
    return SafetyTier.DESTRUCTIVE


def requires_human_approval(skill: Skill[object]) -> bool:
    """Whether invoking ``skill`` demands an approval callback that is not configured."""
    return tier_for_skill(skill) is SafetyTier.DESTRUCTIVE


def tier_for_skill_name(name: str) -> SafetyTier:
    """Tier by name, for callers that hold a name rather than an instance."""
    if name in _SAFE_SKILLS:
        return SafetyTier.SAFE
    if name in _SENSITIVE_SKILLS:
        return SafetyTier.SENSITIVE
    return SafetyTier.DESTRUCTIVE
