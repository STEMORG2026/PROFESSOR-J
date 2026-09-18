"""Task Tracker — Todo/Plan/Goal multi-step decomposition.

Modeled on dsh `todo/`, `plan/`, `goal/` packages.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TodoItem:
    """A single todo item."""

    todo_id: str
    title: str
    description: str
    status: TaskStatus
    created_at: str
    parent_id: str | None = None
    subtasks: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Goal:
    """A goal with associated todos."""

    goal_id: str
    title: str
    description: str
    status: TaskStatus
    created_at: str
    todos: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Plan:
    """A plan for achieving a goal."""

    plan_id: str
    goal_id: str
    title: str
    steps: list[str]
    status: TaskStatus
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)


class TaskTracker:
    """Track todos, plans, and goals."""

    def __init__(self) -> None:
        self._todos: dict[str, TodoItem] = {}
        self._goals: dict[str, Goal] = {}
        self._plans: dict[str, Plan] = {}

    def create_todo(self, title: str, description: str = "", **metadata: Any) -> TodoItem:
        """Create a new todo item."""
        todo_id = str(uuid.uuid4())
        todo = TodoItem(
            todo_id=todo_id,
            title=title,
            description=description,
            status=TaskStatus.PENDING,
            created_at=datetime.now(UTC).isoformat(),
            metadata=metadata,
        )
        self._todos[todo_id] = todo
        return todo

    def create_goal(self, title: str, description: str = "", **metadata: Any) -> Goal:
        """Create a new goal."""
        goal_id = str(uuid.uuid4())
        goal = Goal(
            goal_id=goal_id,
            title=title,
            description=description,
            status=TaskStatus.PENDING,
            created_at=datetime.now(UTC).isoformat(),
            metadata=metadata,
        )
        self._goals[goal_id] = goal
        return goal

    def create_plan(
        self, goal_id: str, title: str, steps: list[str], **metadata: Any
    ) -> Plan | None:
        """Create a plan for a goal."""
        if goal_id not in self._goals:
            return None
        plan_id = str(uuid.uuid4())
        plan = Plan(
            plan_id=plan_id,
            goal_id=goal_id,
            title=title,
            steps=steps,
            status=TaskStatus.PENDING,
            created_at=datetime.now(UTC).isoformat(),
            metadata=metadata,
        )
        self._plans[plan_id] = plan
        return plan

    def decompose_goal(self, goal_id: str, substeps: list[str]) -> list[TodoItem] | None:
        """Decompose a goal into todos."""
        goal = self._goals.get(goal_id)
        if not goal:
            return None
        todos = []
        for substep in substeps:
            todo = self.create_todo(title=substep, parent_id=goal_id)
            goal.todos.append(todo.todo_id)
            todos.append(todo)
        return todos

    def complete_todo(self, todo_id: str) -> bool:
        """Mark a todo as completed."""
        todo = self._todos.get(todo_id)
        if not todo:
            return False
        todo.status = TaskStatus.COMPLETED
        return True

    def list_todos(self) -> list[TodoItem]:
        """List all todos."""
        return list(self._todos.values())

    def list_goals(self) -> list[Goal]:
        """List all goals."""
        return list(self._goals.values())

    def list_plans(self) -> list[Plan]:
        """List all plans."""
        return list(self._plans.values())


def create_task_tracker() -> TaskTracker:
    """Create a task tracker."""
    return TaskTracker()


__all__ = ["TaskTracker", "TodoItem", "Goal", "Plan", "TaskStatus", "create_task_tracker"]
