"""Execution Plan Types — Structured plans for multi-step execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from app.domain.tool import SafetyTier, ApprovalState


class PlanStatus(str, Enum):
    """Overall status of an execution plan."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    """Status of an individual execution step."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class ToolCallRequest:
    """Request to execute a tool with safety metadata."""

    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    safety_tier: SafetyTier = SafetyTier.SAFE
    description: str = ""
    approval_state: ApprovalState = ApprovalState.PENDING
    hitl_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def requires_hitl(self) -> bool:
        """Whether this tool call requires Human-in-the-Loop approval."""
        return self.safety_tier == SafetyTier.DESTRUCTIVE


@dataclass(frozen=True, slots=True)
class ExecutionStep:
    """A single step in an execution plan."""

    step_id: str
    title: str
    tool_call: ToolCallRequest | None = None
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_terminal(self) -> bool:
        """Whether the step has reached a terminal state."""
        return self.status in (
            StepStatus.COMPLETED,
            StepStatus.FAILED,
            StepStatus.REJECTED,
            StepStatus.SKIPPED,
        )

    def can_execute(self) -> bool:
        """Whether the step can be executed (dependencies met, approved)."""
        if self.status != StepStatus.PENDING:
            return False
        if self.tool_call and self.tool_call.requires_hitl():
            return self.tool_call.approval_state == ApprovalState.HITL_APPROVED
        return True


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """
    Structured execution plan with ordered steps.

    Immutable, serializable, supports HITL pauses and resumption.
    """

    plan_id: str = field(default_factory=lambda: f"plan-{uuid4().hex[:8]}")
    goal: str = ""
    steps: tuple[ExecutionStep, ...] = field(default_factory=tuple)
    status: PlanStatus = PlanStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def current_step(self) -> ExecutionStep | None:
        """Get the first non-terminal step."""
        for step in self.steps:
            if not step.is_terminal():
                return step
        return None

    def pending_steps(self) -> tuple[ExecutionStep, ...]:
        """Get all pending steps."""
        return tuple(step for step in self.steps if step.status == StepStatus.PENDING)

    def completed_steps(self) -> tuple[ExecutionStep, ...]:
        """Get all completed steps."""
        return tuple(step for step in self.steps if step.status == StepStatus.COMPLETED)

    def failed_steps(self) -> tuple[ExecutionStep, ...]:
        """Get all failed steps."""
        return tuple(step for step in self.steps if step.status == StepStatus.FAILED)

    def is_complete(self) -> bool:
        """Whether all steps are in terminal states."""
        return all(step.is_terminal() for step in self.steps)

    def has_pending_hitl(self) -> bool:
        """Whether any step is awaiting HITL approval."""
        return any(
            step.tool_call
            and step.tool_call.requires_hitl()
            and step.tool_call.approval_state == ApprovalState.HITL_REQUIRED
            for step in self.steps
        )

    def next_executable_step(self) -> ExecutionStep | None:
        """Get the next step that can be executed."""
        for step in self.steps:
            if step.can_execute():
                return step
        return None

    def with_step_update(self, step_id: str, **updates: Any) -> ExecutionPlan:
        """Return new plan with updated step (immutable update)."""
        import dataclasses

        new_steps = []
        for step in self.steps:
            if step.step_id == step_id:
                new_steps.append(
                    step.__class__(**{**dataclasses.asdict(step), **updates})
                )
            else:
                new_steps.append(step)
        return ExecutionPlan(
            plan_id=self.plan_id,
            goal=self.goal,
            steps=tuple(new_steps),
            status=self.status,
            created_at=self.created_at,
            updated_at=datetime.utcnow(),
            metadata=self.metadata,
        )

    def with_status(self, status: PlanStatus) -> ExecutionPlan:
        """Return new plan with updated status."""
        return ExecutionPlan(
            plan_id=self.plan_id,
            goal=self.goal,
            steps=self.steps,
            status=status,
            created_at=self.created_at,
            updated_at=datetime.utcnow(),
            metadata=self.metadata,
        )
