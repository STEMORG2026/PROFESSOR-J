"""Tests for MCP Server Manager."""

from __future__ import annotations

import pytest

from app.mcp.manager import MCPServerConfig, MCPServerManager, MCPTool


class TestMCPServerConfig:
    def test_stdio_config(self) -> None:
        config = MCPServerConfig(
            name="test-stdio",
            transport_type="stdio",
            command=["python", "-m", "test_server"],
        )
        assert config.name == "test-stdio"
        assert config.transport_type == "stdio"
        assert config.command == ["python", "-m", "test_server"]

    def test_http_config(self) -> None:
        config = MCPServerConfig(
            name="test-http",
            transport_type="http",
            url="http://localhost:8000",
            headers={"Authorization": "Bearer token"},
        )
        assert config.name == "test-http"
        assert config.transport_type == "http"
        assert config.url == "http://localhost:8000"

    def test_stdio_requires_command(self) -> None:
        manager = MCPServerManager()
        config = MCPServerConfig(name="test", transport_type="stdio")
        with pytest.raises(ValueError, match="requires command"):
            manager.register_server(config)

    def test_http_requires_url(self) -> None:
        manager = MCPServerManager()
        config = MCPServerConfig(name="test", transport_type="http")
        with pytest.raises(ValueError, match="requires url"):
            manager.register_server(config)


class TestMCPTool:
    def test_creation(self) -> None:
        tool = MCPTool(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object", "properties": {"arg": {"type": "string"}}},
            server_name="server1",
        )
        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert tool.server_name == "server1"


class TestMCPServerManager:
    @pytest.mark.asyncio
    async def test_register_stdio_server(self) -> None:
        manager = MCPServerManager()
        config = MCPServerConfig(
            name="test-stdio",
            transport_type="stdio",
            command=["echo", "test"],
        )
        manager.register_server(config)
        assert "test-stdio" in manager._servers
        assert "test-stdio" in manager._transports

    @pytest.mark.asyncio
    async def test_register_http_server(self) -> None:
        manager = MCPServerManager()
        config = MCPServerConfig(
            name="test-http",
            transport_type="http",
            url="http://localhost:8000",
        )
        manager.register_server(config)
        assert "test-http" in manager._servers
        assert "test-http" in manager._transports

    @pytest.mark.asyncio
    async def test_list_tools_empty(self) -> None:
        manager = MCPServerManager()
        tools = manager.list_tools()
        assert tools == []

    @pytest.mark.asyncio
    async def test_get_tool_not_found(self) -> None:
        manager = MCPServerManager()
        tool = manager.get_tool("nonexistent")
        assert tool is None

    @pytest.mark.asyncio
    async def test_call_tool_not_found(self) -> None:
        manager = MCPServerManager()
        with pytest.raises(ValueError, match="Tool not found"):
            await manager.call_tool("nonexistent", {})

    @pytest.mark.asyncio
    async def test_call_tool_server_not_connected(self) -> None:
        # With a wired safety policy, a call to a disconnected server raises "not connected".
        from app.domain.tool import SafetyTier
        from app.guardrails.policy import SafetyPolicy

        manager = MCPServerManager(policy=SafetyPolicy(approval_callback=None))
        tool = MCPTool(
            name="test_tool",
            description="Test",
            input_schema={},
            server_name="server1",
            tier=SafetyTier.SAFE,
        )
        manager._tools["test_tool"] = tool
        # Server not connected
        with pytest.raises(RuntimeError, match="not connected"):
            await manager.call_tool("test_tool", {})

    @pytest.mark.asyncio
    async def test_call_tool_fails_closed_without_policy(self) -> None:
        # Phase-2 security boundary: an MCP tool call with NO safety policy wired is refused
        # before reaching the transport. Closes the audit's latent MCP bypass.
        from app.exceptions import SafetyGateError

        manager = MCPServerManager()  # no policy
        tool = MCPTool(name="test_tool", description="Test", input_schema={}, server_name="s1")
        manager._tools["test_tool"] = tool
        with pytest.raises(SafetyGateError):
            await manager.call_tool("test_tool", {})

    @pytest.mark.asyncio
    async def test_get_server_tools(self) -> None:
        manager = MCPServerManager()
        manager._server_tools["server1"] = ["tool1", "tool2"]
        manager._tools["tool1"] = MCPTool("tool1", "desc", {}, "server1")
        manager._tools["tool2"] = MCPTool("tool2", "desc", {}, "server1")
        manager._tools["tool3"] = MCPTool("tool3", "desc", {}, "server2")

        tools = manager.get_server_tools("server1")
        assert len(tools) == 2
        assert all(t.server_name == "server1" for t in tools)
