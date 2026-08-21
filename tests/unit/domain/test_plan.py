"""Tests for domain plan types."""

from __future__ import annotations

import pytest
from datetime import datetime

from app.domain.plan import (
    ExecutionPlan,
    ExecutionStep,
    PlanStatus,
    StepStatus,
    ToolCallRequest,
)
from app.domain.tool import SafetyTier, ApprovalState


class TestToolCallRequest:
    def test_safe_tool_no_hitl(self):
        req = ToolCallRequest(
            tool="lookup_concept",
            args={"concept_id": "lhs:phys.force"},
            safety_tier=SafetyTier.SAFE,
        )
        assert req.requires_hitl() is False

    def test_destructive_tool_requires_hitl(self):
        req = ToolCallRequest(
            tool="execute_python_code",
            args={"code": "print('hello')"},
            safety_tier=SafetyTier.DESTRUCTIVE,
        )
        assert req.requires_hitl() is True

    def test_approval_state_default(self):
        req = ToolCallRequest(tool="test", args={}, safety_tier=SafetyTier.SAFE)
        assert req.approval_state == ApprovalState.PENDING


class TestExecutionStep:
    def test_pending_step_can_execute(self):
        step = ExecutionStep(
            step_id="s1",
            title="Test step",
            status=StepStatus.PENDING,
        )
        assert step.can_execute() is True
        assert step.is_terminal() is False

    def test_step_with_safe_tool_can_execute(self):
        step = ExecutionStep(
            step_id="s1",
            title="Lookup",
            tool_call=ToolCallRequest(
                tool="lookup_concept",
                args={"concept_id": "lhs:phys.force"},
                safety_tier=SafetyTier.SAFE,
            ),
            status=StepStatus.PENDING,
        )
        assert step.can_execute() is True

    def test_step_with_destructive_tool_awaits_approval(self):
        step = ExecutionStep(
            step_id="s1",
            title="Execute code",
            tool_call=ToolCallRequest(
                tool="execute_python_code",
                args={"code": "print(1)"},
                safety_tier=SafetyTier.DESTRUCTIVE,
            ),
            status=StepStatus.PENDING,
        )
        assert step.can_execute() is False

    def test_step_with_approved_destructive_tool_can_execute(self):
        step = ExecutionStep(
            step_id="s1",
            title="Execute code",
            tool_call=ToolCallRequest(
                tool="execute_python_code",
                args={"code": "print(1)"},
                safety_tier=SafetyTier.DESTRUCTIVE,
                approval_state=ApprovalState.HITL_APPROVED,
            ),
            status=StepStatus.PENDING,
        )
        assert step.can_execute() is True

    def test_terminal_states(self):
        for status in (
            StepStatus.COMPLETED,
            StepStatus.FAILED,
            StepStatus.REJECTED,
            StepStatus.SKIPPED,
        ):
            step = ExecutionStep(step_id="s1", title="Test", status=status)
            assert step.is_terminal() is True

    def test_non_terminal_states(self):
        for status in (
            StepStatus.PENDING,
            StepStatus.IN_PROGRESS,
            StepStatus.AWAITING_APPROVAL,
            StepStatus.APPROVED,
        ):
            step = ExecutionStep(step_id="s1", title="Test", status=status)
            assert step.is_terminal() is False


class TestExecutionPlan:
    def test_empty_plan(self):
        plan = ExecutionPlan(goal="Test goal")
        assert plan.plan_id.startswith("plan-")
        assert plan.goal == "Test goal"
        assert plan.steps == ()
        assert plan.status == PlanStatus.PENDING
        assert plan.is_complete() is True  # No steps = complete

    def test_plan_with_steps(self):
        step1 = ExecutionStep(step_id="s1", title="Step 1", status=StepStatus.PENDING)
        step2 = ExecutionStep(step_id="s2", title="Step 2", status=StepStatus.PENDING)
        plan = ExecutionPlan(goal="Test", steps=(step1, step2))
        assert len(plan.steps) == 2
        assert plan.is_complete() is False

    def test_current_step(self):
        step1 = ExecutionStep(step_id="s1", title="Step 1", status=StepStatus.COMPLETED)
        step2 = ExecutionStep(step_id="s2", title="Step 2", status=StepStatus.PENDING)
        step3 = ExecutionStep(step_id="s3", title="Step 3", status=StepStatus.PENDING)
        plan = ExecutionPlan(goal="Test", steps=(step1, step2, step3))
        current = plan.current_step()
        assert current is not None
        assert current.step_id == "s2"

    def test_pending_steps(self):
        step1 = ExecutionStep(step_id="s1", title="Step 1", status=StepStatus.COMPLETED)
        step2 = ExecutionStep(step_id="s2", title="Step 2", status=StepStatus.PENDING)
        step3 = ExecutionStep(step_id="s3", title="Step 3", status=StepStatus.FAILED)
        plan = ExecutionPlan(goal="Test", steps=(step1, step2, step3))
        pending = plan.pending_steps()
        assert len(pending) == 1
        assert pending[0].step_id == "s2"

    def test_completed_steps(self):
        step1 = ExecutionStep(step_id="s1", title="Step 1", status=StepStatus.COMPLETED)
        step2 = ExecutionStep(step_id="s2", title="Step 2", status=StepStatus.PENDING)
        plan = ExecutionPlan(goal="Test", steps=(step1, step2))
        completed = plan.completed_steps()
        assert len(completed) == 1
        assert completed[0].step_id == "s1"

    def test_failed_steps(self):
        step1 = ExecutionStep(step_id="s1", title="Step 1", status=StepStatus.COMPLETED)
        step2 = ExecutionStep(step_id="s2", title="Step 2", status=StepStatus.FAILED)
        plan = ExecutionPlan(goal="Test", steps=(step1, step2))
        failed = plan.failed_steps()
        assert len(failed) == 1
        assert failed[0].step_id == "s2"

    def test_is_complete(self):
        plan = ExecutionPlan(goal="Test")
        assert plan.is_complete() is True

        step1 = ExecutionStep(step_id="s1", title="Step 1", status=StepStatus.COMPLETED)
        step2 = ExecutionStep(step_id="s2", title="Step 2", status=StepStatus.COMPLETED)
        plan2 = ExecutionPlan(goal="Test", steps=(step1, step2))
        assert plan2.is_complete() is True

        step3 = ExecutionStep(step_id="s3", title="Step 3", status=StepStatus.PENDING)
        plan3 = ExecutionPlan(goal="Test", steps=(step1, step2, step3))
        assert plan3.is_complete() is False

    def test_has_pending_hitl(self):
        step1 = ExecutionStep(
            step_id="s1",
            title="Safe",
            tool_call=ToolCallRequest(tool="lookup", args={}, safety_tier=SafetyTier.SAFE),
            status=StepStatus.PENDING,
        )
        step2 = ExecutionStep(
            step_id="s2",
            title="Destructive",
            tool_call=ToolCallRequest(
                tool="execute", args={}, safety_tier=SafetyTier.DESTRUCTIVE,
                approval_state=ApprovalState.HITL_REQUIRED
            ),
            status=StepStatus.PENDING,
        )
        plan = ExecutionPlan(goal="Test", steps=(step1, step2))
        assert plan.has_pending_hitl() is True

    def test_next_executable_step(self):
        step1 = ExecutionStep(step_id="s1", title="Step 1", status=StepStatus.COMPLETED)
        step2 = ExecutionStep(step_id="s2", title="Step 2", status=StepStatus.PENDING)
        step3 = ExecutionStep(step_id="s3", title="Step 3", status=StepStatus.PENDING)
        plan = ExecutionPlan(goal="Test", steps=(step1, step2, step3))
        next_step = plan.next_executable_step()
        assert next_step is not None
        assert next_step.step_id == "s2"

    def test_with_step_update(self):
        step1 = ExecutionStep(step_id="s1", title="Step 1", status=StepStatus.PENDING)
        step2 = ExecutionStep(step_id="s2", title="Step 2", status=StepStatus.PENDING)
        plan = ExecutionPlan(goal="Test", steps=(step1, step2))

        updated = plan.with_step_update("s1", status=StepStatus.COMPLETED)
        assert updated.steps[0].status == StepStatus.COMPLETED
        assert updated.steps[1].status == StepStatus.PENDING
        # Original unchanged
        assert plan.steps[0].status == StepStatus.PENDING

    def test_with_status(self):
        plan = ExecutionPlan(goal="Test", status=PlanStatus.PENDING)
        updated = plan.with_status(PlanStatus.IN_PROGRESS)
        assert updated.status == PlanStatus.IN_PROGRESS
        assert updated.updated_at > plan.updated_at
        # Original unchanged
        assert plan.status == PlanStatus.PENDING


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
