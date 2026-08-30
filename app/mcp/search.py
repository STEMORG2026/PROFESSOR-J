"""MCP Tool Search - on-demand tool discovery and filtering."""

from __future__ import annotations

import logging
from typing import Any

from app.mcp.manager import MCPServerManager, MCPTool

logger = logging.getLogger(__name__)


class MCPToolSearch:
    """Provides on-demand tool search and filtering across MCP servers."""

    def __init__(self, manager: MCPServerManager) -> None:
        self._manager = manager

    async def search_tools(self, query: str, max_results: int = 10) -> list[MCPTool]:
        """Search for tools matching a query string."""
        all_tools = self._manager.list_tools()
        query_lower = query.lower()

        # Simple text matching against name and description
        matches = []
        for tool in all_tools:
            score = 0
            if query_lower in tool.name.lower():
                score += 10
            if query_lower in tool.description.lower():
                score += 5
            # Check input schema properties
            for prop in tool.input_schema.get("properties", {}):
                if query_lower in prop.lower():
                    score += 2
            if score > 0:
                matches.append((score, tool))

        matches.sort(key=lambda x: x[0], reverse=True)
        return [tool for _, tool in matches[:max_results]]

    async def find_tool_for_task(self, task_description: str) -> MCPTool | None:
        """Find the best tool for a given task description."""
        results = await self.search_tools(task_description, max_results=1)
        return results[0] if results else None

    def list_tools_by_server(self) -> dict[str, list[MCPTool]]:
        """List all tools grouped by server."""
        result = {}
        for server_name in self._manager._server_tools:
            result[server_name] = self._manager.get_server_tools(server_name)
        return result

    def filter_tools_by_schema(self, required_params: list[str]) -> list[MCPTool]:
        """Filter tools that accept all required parameters."""
        all_tools = self._manager.list_tools()
        filtered = []
        for tool in all_tools:
            props = tool.input_schema.get("properties", {})
            if all(param in props for param in required_params):
                filtered.append(tool)
        return filtered

    async def call_best_tool(self, task: str, arguments: dict[str, Any]) -> Any:
        """Find the best tool for a task and call it."""
        tool = await self.find_tool_for_task(task)
        if not tool:
            raise ValueError(f"No suitable tool found for task: {task}")
        return await self._manager.call_tool(tool.name, arguments)

    def get_code_execution_tools(self) -> list[MCPTool]:
        """Get tools that provide code execution capabilities (CodeExecutionTools pattern)."""
        all_tools = self._manager.list_tools()
        return [
            tool
            for tool in all_tools
            if "code" in tool.name.lower()
            or "exec" in tool.name.lower()
            or "python" in tool.name.lower()
        ]
