"""Tests for app.mcp.registry — registry, on-demand search, code-tool adapter."""

from __future__ import annotations

from typing import Any

import pytest

from app.mcp import MCPResource, MCPTool
from app.mcp.registry import (
    CodeExecutionTools,
    MCPRegistry,
    MCPServerManager,
    MCPToolSearch,
)


def _tool(name: str, server: str = "svc", desc: str = "desc") -> MCPTool:
    return MCPTool(
        name=name,
        description=desc,
        input_schema={"type": "object"},
        server_id=server,
    )


class FakeManager:
    """A minimal stand-in for MCPClientManager with a fixed tool/resource set."""

    def __init__(self, tools: list[MCPTool], resources: list[MCPResource]) -> None:
        self.tools = tools
        self.resources = resources
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.call_log: list[tuple[str, str, dict[str, Any]]] = []

    def list_tools(self) -> list[MCPTool]:
        return list(self.tools)

    def list_resources(self) -> list[MCPResource]:
        return list(self.resources)

    async def connect_all(self) -> dict[str, bool]:
        self.connect_calls += 1
        return {t.server_id: True for t in self.tools}

    async def disconnect_all(self) -> None:
        self.disconnect_calls += 1

    async def call_tool(
        self, server_id: str, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        self.call_log.append((server_id, tool_name, arguments))
        return {"ok": True}


class TestMCPRegistry:
    def test_cache_tools_list_caches_and_filters(self) -> None:
        manager = FakeManager(
            [_tool("read_file", "fs"), _tool("write_file", "fs"), _tool("memo", "mem")],
            [],
        )
        registry = MCPRegistry(manager)
        assert {t.name for t in registry.cache_tools_list()} == {
            "read_file",
            "write_file",
            "memo",
        }
        # Second call is served from cache (no re-list from the manager).
        registry.cache_tools_list()
        fs_tools = registry.tools_by_server("fs")
        assert {t.name for t in fs_tools} == {"read_file", "write_file"}
        assert registry.resources_by_server("fs") == []
        registry.invalidate_tools()

    def test_resources_by_server(self) -> None:
        res = MCPResource(
            uri="mem://k", name="k", description=None, mime_type=None, server_id="mem"
        )
        registry = MCPRegistry(FakeManager([], [res]))
        assert [r.uri for r in registry.resources_by_server("mem")] == ["mem://k"]
        assert registry.resources_by_server("fs") == []


class TestMCPToolSearch:
    def test_search_and_lazy_schema(self) -> None:
        registry = MCPRegistry(
            FakeManager(
                [_tool("read_file", "fs", "Read files from disk"), _tool("list_dir", "fs")],
                [],
            )
        )
        search = MCPToolSearch(registry)
        hits = search.search("read", "fs")
        assert [t.name for t in hits] == ["read_file"]
        schema = search.tool_schema("fs", "read_file")
        assert schema == {"type": "object"}
        # Unknown tool raises.
        with pytest.raises(KeyError):
            search.tool_schema("fs", "missing")

    def test_compiled_list_is_compact(self) -> None:
        registry = MCPRegistry(FakeManager([_tool("a", "fs", "A tool")], []))
        search = MCPToolSearch(registry)
        view = search.compiled_list("fs")
        assert view == [{"server_id": "fs", "name": "a", "description": "A tool"}]
        assert "input_schema" not in view[0]


class TestCodeExecutionTools:
    async def test_call_by_dotted_name(self) -> None:
        manager = FakeManager([_tool("read_file", "fs")], [])
        code = CodeExecutionTools(manager)
        out = await code.call("fs.read_file", path="/tmp/x")
        assert out == {"ok": True}
        assert manager.call_log == [("fs", "read_file", {"path": "/tmp/x"})]
        with pytest.raises(ValueError):
            code.resolve("not-dotted")


class TestMCPServerManager:
    async def test_facade_plumbs_registry_and_code(self) -> None:
        manager = FakeManager([_tool("read_file", "fs")], [])
        sm = MCPServerManager(manager)
        assert sm.cache_tools_list()[0].name == "read_file"
        assert sm.search.search("read", "fs")[0].name == "read_file"
        out = await sm.code.call("fs.read_file")
        assert out == {"ok": True}
        results = await sm.connect_all()
        assert results["fs"] is True
        await sm.disconnect_all()
        assert manager.disconnect_calls == 1
