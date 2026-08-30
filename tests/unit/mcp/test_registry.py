"""Tests for MCP Registry."""

from __future__ import annotations

from pathlib import Path

from app.mcp.manager import MCPServerConfig, MCPTool
from app.mcp.registry import MCPRegistry


class TestMCPRegistry:
    def test_register_server(self) -> None:
        registry = MCPRegistry()
        config = MCPServerConfig(name="server1", transport_type="stdio", command=["echo"])
        registry.register_server(config)
        assert registry.get_server_config("server1") == config

    def test_list_server_configs(self) -> None:
        registry = MCPRegistry()
        config1 = MCPServerConfig(name="server1", transport_type="stdio", command=["echo"])
        config2 = MCPServerConfig(name="server2", transport_type="http", url="http://localhost")
        registry.register_server(config1)
        registry.register_server(config2)
        configs = registry.list_server_configs()
        assert len(configs) == 2

    def test_remove_server(self) -> None:
        registry = MCPRegistry()
        config = MCPServerConfig(name="server1", transport_type="stdio", command=["echo"])
        registry.register_server(config)
        assert registry.remove_server("server1") is True
        assert registry.get_server_config("server1") is None
        assert registry.remove_server("nonexistent") is False

    def test_cache_tools(self) -> None:
        registry = MCPRegistry()
        tools = [
            MCPTool("tool1", "desc1", {}, "server1"),
            MCPTool("tool2", "desc2", {}, "server1"),
        ]
        registry.cache_tools("server1", tools)
        cached = registry.get_cached_tools("server1")
        assert len(cached) == 2
        assert all(t.server_name == "server1" for t in cached)

    def test_cache_tools_list(self) -> None:
        registry = MCPRegistry()
        registry.cache_tools_list("server1", ["tool1", "tool2"])
        assert registry.has_cached_tools("server1") is True
        assert registry._server_tools["server1"] == ["tool1", "tool2"]

    def test_get_all_cached_tools(self) -> None:
        registry = MCPRegistry()
        tools = [
            MCPTool("tool1", "desc1", {}, "server1"),
            MCPTool("tool2", "desc2", {}, "server2"),
        ]
        registry.cache_tools("server1", [tools[0]])
        registry.cache_tools("server2", [tools[1]])
        all_tools = registry.get_all_cached_tools()
        assert len(all_tools) == 2

    def test_clear_cache_server(self) -> None:
        registry = MCPRegistry()
        tools = [MCPTool("tool1", "desc1", {}, "server1")]
        registry.cache_tools("server1", tools)
        registry.clear_cache("server1")
        assert registry.has_cached_tools("server1") is False
        assert registry.get_cached_tools("server1") == []

    def test_clear_cache_all(self) -> None:
        registry = MCPRegistry()
        tools = [MCPTool("tool1", "desc1", {}, "server1")]
        registry.cache_tools("server1", tools)
        registry.clear_cache()
        assert registry.get_all_cached_tools() == []
        assert registry._server_tools == {}

    def test_save_load(self, tmp_path: Path) -> None:
        cache_path = tmp_path / "mcp_registry.json"
        registry = MCPRegistry(cache_path)
        config = MCPServerConfig(name="server1", transport_type="stdio", command=["echo"])
        registry.register_server(config)
        tools = [MCPTool("tool1", "desc1", {"type": "object"}, "server1")]
        registry.cache_tools("server1", tools)
        registry.save()

        # Create new registry and load
        registry2 = MCPRegistry(cache_path)
        loaded = registry2.load()
        assert loaded is True
        assert registry2.get_server_config("server1") is not None
        assert len(registry2.get_all_cached_tools()) == 1

    def test_load_nonexistent(self, tmp_path: Path) -> None:
        cache_path = tmp_path / "nonexistent.json"
        registry = MCPRegistry(cache_path)
        loaded = registry.load()
        assert loaded is False
