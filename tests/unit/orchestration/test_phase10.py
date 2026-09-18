"""Tests for Phase 10 orchestration components."""

from __future__ import annotations

import pytest

from app.orchestration import (
    Scheduler,
    SessionManager,
    TaskStatus,
    TaskTracker,
    ToolSearch,
    create_sandbox,
    create_scheduler,
    create_session_manager,
    create_task_tracker,
    create_tool_search,
)


class TestSessionManager:
    """Test session management."""

    @pytest.fixture
    def manager(self) -> SessionManager:
        return create_session_manager()

    def test_create_session(self, manager: SessionManager) -> None:
        session = manager.create_session("Test Session")
        assert session.title == "Test Session"
        assert session.session_id is not None

    def test_fork_session(self, manager: SessionManager) -> None:
        original = manager.create_session("Original")
        fork = manager.fork_session(original.session_id)
        assert fork is not None
        assert fork.parent_id == original.session_id
        assert fork.session_id != original.session_id

    def test_export_import(self, manager: SessionManager) -> None:
        session = manager.create_session("Export Test")
        exported = manager.export_session(session.session_id)
        assert exported is not None
        imported = manager.import_session(exported)
        assert imported is not None
        assert imported.title == "Export Test"


class TestToolSearch:
    """Test tool search."""

    @pytest.fixture
    def search(self) -> ToolSearch:
        return create_tool_search()

    def test_register_and_search(self, search: ToolSearch) -> None:
        search.register_tool("code_search", "Search code", "dsh", "search")
        search.register_tool("web_fetch", "Fetch web content", "hermes", "fetch")
        results = search.search("search")
        assert len(results) == 1
        assert results[0].name == "code_search"


class TestSandbox:
    """Test sandboxed execution."""

    @pytest.mark.asyncio
    async def test_execute_command(self) -> None:
        sandbox = create_sandbox()
        result = await sandbox.execute_command(["echo", "hello"])
        assert result.exit_code == 0
        assert "hello" in result.stdout


class TestTaskTracker:
    """Test task tracking."""

    @pytest.fixture
    def tracker(self) -> TaskTracker:
        return create_task_tracker()

    def test_create_todo(self, tracker: TaskTracker) -> None:
        todo = tracker.create_todo("Test Todo")
        assert todo.title == "Test Todo"
        assert todo.status == TaskStatus.PENDING

    def test_create_goal_and_plan(self, tracker: TaskTracker) -> None:
        goal = tracker.create_goal("Learn Python", "Master Python programming")
        plan = tracker.create_plan(goal.goal_id, "Study Plan", ["Step 1", "Step 2"])
        assert plan is not None
        assert plan.goal_id == goal.goal_id

    def test_decompose_goal(self, tracker: TaskTracker) -> None:
        goal = tracker.create_goal("Learn Math", "Master algebra and calculus")
        todos = tracker.decompose_goal(goal.goal_id, ["Study algebra", "Study calculus"])
        assert todos is not None
        assert len(todos) == 2


class TestScheduler:
    """Test scheduler."""

    @pytest.fixture
    def scheduler(self) -> Scheduler:
        return create_scheduler()

    def test_add_job(self, scheduler: Scheduler) -> None:
        job = scheduler.add_job("daily_report", "0 9 * * *", "Generate daily report", "professor_j")
        assert job.name == "daily_report"
        assert job.status == "pending"

    def test_list_jobs(self, scheduler: Scheduler) -> None:
        scheduler.add_job("job1", "0 9 * * *", "Task 1", "professor_j")
        scheduler.add_job("job2", "0 10 * * *", "Task 2", "hermes")
        jobs = scheduler.list_jobs()
        assert len(jobs) == 2

    @pytest.mark.asyncio
    async def test_execute_job(self, scheduler: Scheduler) -> None:
        job = scheduler.add_job("test", "0 9 * * *", "Test task", "professor_j")
        result = await scheduler.execute_job(job.job_id)
        assert result is True
