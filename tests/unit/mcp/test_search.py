"""Tests for MCP Tool Search."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.mcp.manager import MCPServerManager, MCPTool
from app.mcp.search import MCPToolSearch


class TestMCPToolSearch:
    @pytest.fixture
    def mock_manager(self) -> MagicMock:
        manager = MagicMock(spec=MCPServerManager)
        return manager

    @pytest.fixture
    def sample_tools(self) -> list[MCPTool]:
        return [
            MCPTool(
                name="run_code",
                description="Execute Python code in sandbox",
                input_schema={"type": "object", "properties": {"code": {"type": "string"}}},
                server_name="code-server",
            ),
            MCPTool(
                name="search_web",
                description="Search the web for information",
                input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
                server_name="web-server",
            ),
            MCPTool(
                name="python_exec",
                description="Execute Python script",
                input_schema={"type": "object", "properties": {"script": {"type": "string"}}},
                server_name="code-server",
            ),
            MCPTool(
                name="read_file",
                description="Read a file from disk",
                input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
                server_name="fs-server",
            ),
        ]

    def test_search_tools_by_name(
        self, mock_manager: MagicMock, sample_tools: list[MCPTool]
    ) -> None:
        mock_manager.list_tools.return_value = sample_tools
        search = MCPToolSearch(mock_manager)

        import asyncio

        results = asyncio.run(search.search_tools("code", max_results=10))
        assert len(results) == 1
        assert results[0].name == "run_code"

    def test_search_tools_by_name_exec(
        self, mock_manager: MagicMock, sample_tools: list[MCPTool]
    ) -> None:
        mock_manager.list_tools.return_value = sample_tools
        search = MCPToolSearch(mock_manager)

        import asyncio

        results = asyncio.run(search.search_tools("exec", max_results=10))
        # "python_exec" has exec in name, "run_code" has "execute" in description
        assert len(results) == 2
        names = [t.name for t in results]
        assert "python_exec" in names
        assert "run_code" in names

    def test_search_tools_by_description(
        self, mock_manager: MagicMock, sample_tools: list[MCPTool]
    ) -> None:
        mock_manager.list_tools.return_value = sample_tools
        search = MCPToolSearch(mock_manager)

        import asyncio

        results = asyncio.run(search.search_tools("sandbox", max_results=10))
        assert len(results) >= 1
        assert any("sandbox" in t.description.lower() for t in results)

    def test_search_tools_max_results(
        self, mock_manager: MagicMock, sample_tools: list[MCPTool]
    ) -> None:
        mock_manager.list_tools.return_value = sample_tools
        search = MCPToolSearch(mock_manager)

        import asyncio

        results = asyncio.run(search.search_tools("exec", max_results=1))
        assert len(results) == 1

    def test_find_tool_for_task(self, mock_manager: MagicMock, sample_tools: list[MCPTool]) -> None:
        mock_manager.list_tools.return_value = sample_tools
        search = MCPToolSearch(mock_manager)

        import asyncio

        tool = asyncio.run(search.find_tool_for_task("execute python code"))
        assert tool is not None
        assert tool.name == "run_code"

    def test_find_tool_for_task_no_match(
        self, mock_manager: MagicMock, sample_tools: list[MCPTool]
    ) -> None:
        mock_manager.list_tools.return_value = sample_tools
        search = MCPToolSearch(mock_manager)

        import asyncio

        tool = asyncio.run(search.find_tool_for_task("something completely unrelated"))
        assert tool is None

    def test_list_tools_by_server(
        self, mock_manager: MagicMock, sample_tools: list[MCPTool]
    ) -> None:
        mock_manager._server_tools = {
            "code-server": ["run_code", "python_exec"],
            "web-server": ["search_web"],
        }
        mock_manager.get_server_tools.side_effect = lambda name: [
            t for t in sample_tools if t.server_name == name
        ]
        search = MCPToolSearch(mock_manager)

        result = search.list_tools_by_server()
        assert "code-server" in result
        assert "web-server" in result
        assert len(result["code-server"]) == 2
        assert len(result["web-server"]) == 1

    def test_filter_tools_by_schema(
        self, mock_manager: MagicMock, sample_tools: list[MCPTool]
    ) -> None:
        mock_manager.list_tools.return_value = sample_tools
        search = MCPToolSearch(mock_manager)

        results = search.filter_tools_by_schema(["query"])
        assert len(results) == 1
        assert results[0].name == "search_web"

    def test_get_code_execution_tools(
        self, mock_manager: MagicMock, sample_tools: list[MCPTool]
    ) -> None:
        mock_manager.list_tools.return_value = sample_tools
        search = MCPToolSearch(mock_manager)

        results = search.get_code_execution_tools()
        assert len(results) == 2
        assert all(
            "code" in t.name.lower() or "exec" in t.name.lower() or "python" in t.name.lower()
            for t in results
        )
