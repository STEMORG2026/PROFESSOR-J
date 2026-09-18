"""Tests for the Subagent Manager."""

from __future__ import annotations

import pytest

from app.orchestration import (
    AgentRouter,
    PluginRegistry,
    SubagentManager,
    create_agent_router,
    create_plugin_registry,
    create_subagent_manager,
)


class TestSubagentManager:
    """Test suite for the Subagent Manager."""

    @pytest.fixture
    def manager(self) -> SubagentManager:
        return create_subagent_manager()

    def test_list_agents_empty(self, manager: SubagentManager) -> None:
        assert manager.list_agents() == []

    def test_get_agent_not_found(self, manager: SubagentManager) -> None:
        assert manager.get_agent("nonexistent") is None


class TestPluginRegistry:
    """Test suite for the Plugin Registry."""

    @pytest.fixture
    def registry(self) -> PluginRegistry:
        return create_plugin_registry()

    def test_register_and_get(self, registry: PluginRegistry) -> None:
        async def handler():
            pass

        registry.register("test", "Test plugin", handler)
        plugin = registry.get("test")
        assert plugin is not None
        assert plugin.name == "test"

    def test_list_plugins(self, registry: PluginRegistry) -> None:
        plugins = registry.list_plugins()
        assert isinstance(plugins, list)

    def test_discover(self, registry: PluginRegistry) -> None:
        async def handler():
            pass

        registry.register("research_helper", "Helps with research", handler)
        results = registry.discover("research")
        assert len(results) >= 1


class TestAgentRouter:
    """Test suite for the Agent Router."""

    @pytest.fixture
    def router(self) -> AgentRouter:
        return create_agent_router()

    def test_classify_research(self, router: AgentRouter) -> None:
        result = router.classify("research the latest AI papers")
        assert result.task_type == "research"
        assert result.recommended_agent == "hermes"

    def test_classify_code(self, router: AgentRouter) -> None:
        result = router.classify("implement a sorting algorithm")
        assert result.task_type == "implementation"
        assert result.recommended_agent == "dsh"

    def test_classify_github(self, router: AgentRouter) -> None:
        result = router.classify("create a PR for this fix")
        assert result.task_type == "github_workflow"
        assert result.recommended_agent == "opencode"

    def test_classify_education(self, router: AgentRouter) -> None:
        result = router.classify("explain Newton's laws")
        assert result.task_type == "education"
        assert result.recommended_agent == "professor_j"

    def test_get_agent_for_task(self, router: AgentRouter) -> None:
        agent = router.get_agent_for_task("search for recent papers")
        assert isinstance(agent, str)
        assert len(agent) > 0
