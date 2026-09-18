"""Agent Router — classify tasks and route to most capable subagent."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TaskClassification:
    """Result of classifying a task."""

    task_type: str
    complexity: str  # simple, moderate, complex
    domain: str  # education, research, code, general
    recommended_agent: str
    confidence: float  # 0.0 to 1.0


class AgentRouter:
    """Routes tasks to the most capable subagent."""

    def __init__(self) -> None:
        self._rules: list[dict[str, Any]] = []

    def add_rule(
        self,
        task_type: str,
        domain: str,
        agent: str,
        priority: int = 0,
    ) -> None:
        """Add a routing rule."""
        self._rules.append(
            {
                "task_type": task_type,
                "domain": domain,
                "agent": agent,
                "priority": priority,
            }
        )

    def classify(self, task_description: str) -> TaskClassification:
        """Classify a task and recommend an agent."""
        desc_lower = task_description.lower()

        # Simple keyword-based classification
        if any(kw in desc_lower for kw in ["research", "find", "search", "paper"]):
            return TaskClassification(
                task_type="research",
                complexity="moderate",
                domain="research",
                recommended_agent="hermes",
                confidence=0.8,
            )
        if any(kw in desc_lower for kw in ["code", "implement", "function", "class"]):
            return TaskClassification(
                task_type="implementation",
                complexity="moderate",
                domain="code",
                recommended_agent="dsh",
                confidence=0.75,
            )
        if any(kw in desc_lower for kw in ["pr", "github", "merge", "branch"]):
            return TaskClassification(
                task_type="github_workflow",
                complexity="simple",
                domain="code",
                recommended_agent="opencode",
                confidence=0.9,
            )
        if any(kw in desc_lower for kw in ["answer", "explain", "concept", "learn"]):
            return TaskClassification(
                task_type="education",
                complexity="simple",
                domain="education",
                recommended_agent="professor_j",
                confidence=0.85,
            )

        return TaskClassification(
            task_type="general",
            complexity="simple",
            domain="general",
            recommended_agent="professor_j",
            confidence=0.5,
        )

    def get_agent_for_task(self, task_description: str) -> str:
        """Get the recommended agent for a task."""
        classification = self.classify(task_description)
        logger.info(
            "Task classified: type=%s domain=%s → agent=%s (confidence=%.2f)",
            classification.task_type,
            classification.domain,
            classification.recommended_agent,
            classification.confidence,
        )
        return classification.recommended_agent


def create_agent_router() -> AgentRouter:
    """Create an agent router with default rules."""
    router = AgentRouter()
    router.add_rule("research", "research", "hermes", priority=10)
    router.add_rule("implementation", "code", "dsh", priority=10)
    router.add_rule("github_workflow", "code", "opencode", priority=20)
    router.add_rule("education", "education", "professor_j", priority=15)
    return router


__all__ = ["AgentRouter", "TaskClassification", "create_agent_router"]
