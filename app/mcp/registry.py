"""MCP registry, on-demand tool search, and code-execution adapter.

Completes the Phase 1 MCP contract described in ``IMPLEMENTATION-PLAN.md`` and
``ARCHITECTURE.md``: a client lives in :mod:`app.mcp` (connection + discovery via
:class:`MCPClientManager`); this module adds the higher layers around it:

- :class:`MCPRegistry` — tool/resource discovery with result caching
  (``cache_tools_list``) and per-run filtering.
- :class:`MCPToolSearch` — on-demand tool definition loading so an agent pulls a
  tool's schema only when it needs it (the Anthropic on-demand pattern) instead
  of loading every tool up front.
- :class:`CodeExecutionTools` — exposes MCP tools as filesystem-style code APIs so
  code executors can call them by dotted name (e.g. ``filesystem.read_file``).
- :class:`MCPServerManager` — the registry + search facade over an
  :class:`MCPClientManager`, giving the board/architecture the expected surface.

These are deliberately thin, typed wrappers: behavior lives in the concrete
clients, and this layer supplies the registry/caching/search contract.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from app.mcp import (
    MCPClientManager,
    MCPResource,
    MCPTool,
)

logger = logging.getLogger(__name__)


class MCPManagerProto(Protocol):
    """Structural surface MCPRegistry/MCPToolSearch/CodeExecutionTools depend on.

    Kept minimal so tests and alternate clients can supply a conforming object
    without subclassing :class:`MCPClientManager`; the real client already
    satisfies it.
    """

    def list_tools(self) -> list[MCPTool]: ...

    def list_resources(self) -> list[MCPResource]: ...

    async def call_tool(
        self, server_id: str, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]: ...

    async def connect_all(self) -> dict[str, bool]: ...

    async def disconnect_all(self) -> None: ...


class MCPRegistry:
    """Discover and cache MCP tools and resources, optionally per run.

    Acts as the discovery + filtering layer described by the architecture's
    ``MCPRegistry``: list tools once, cache the result via
    :meth:`cache_tools_list`, and let each agent/run request a filtered view so
    only the tools relevant to that run are handed to the model.
    """

    def __init__(self, manager: MCPManagerProto) -> None:
        self.manager = manager
        self._cached_tools: list[MCPTool] | None = None
        self._cached_resources: list[MCPResource] | None = None

    def cache_tools_list(self) -> list[MCPTool]:
        """Cache the full tool list, refreshing only when not yet cached."""
        if self._cached_tools is None:
            self._cached_tools = self.manager.list_tools()
        return list(self._cached_tools)

    def invalidate_tools(self) -> None:
        """Drop the cached tool list so the next call re-lists tools."""
        self._cached_tools = None

    def cache_resources_list(self) -> list[MCPResource]:
        """Cache the full resource list, refreshing only when not yet cached."""
        if self._cached_resources is None:
            self._cached_resources = self.manager.list_resources()
        return list(self._cached_resources)

    def invalidate_resources(self) -> None:
        """Drop the cached resource list so the next call re-lists resources."""
        self._cached_resources = None

    def list_tools(self) -> list[MCPTool]:
        """Return all known tools (shortcut to the cached list)."""
        return self.cache_tools_list()

    def list_resources(self) -> list[MCPResource]:
        """Return all known resources (shortcut to the cached list)."""
        return self.cache_resources_list()

    def tools_by_server(self, server_id: str | None = None) -> list[MCPTool]:
        """Filter cached tools to one server (or all when ``server_id`` is None)."""
        tools = self.cache_tools_list()
        if server_id is None:
            return tools
        return [t for t in tools if t.server_id == server_id]

    def resources_by_server(self, server_id: str | None = None) -> list[MCPResource]:
        """Filter cached resources to one server (or all when ``server_id`` is None)."""
        resources = self.cache_resources_list()
        if server_id is None:
            return resources
        return [r for r in resources if r.server_id == server_id]


class MCPToolSearch:
    """On-demand MCP tool resolution.

    A tool is only fully materialized (schema fetched) when requested, so the
    model sees a compact list of tool *names/descriptions* up front and pulls
    the full ``input_schema`` lazily — the on-demand loading pattern that keeps
    context small.
    """

    def __init__(self, registry: MCPRegistry) -> None:
        self.registry = registry
        self._schema_cache: dict[str, dict[str, Any]] = {}

    def search(self, query: str, server_id: str | None = None) -> list[MCPTool]:
        """Return tools whose name or description matches ``query``."""
        q = query.lower()
        return [
            t
            for t in self.registry.tools_by_server(server_id)
            if q in t.name.lower() or q in t.description.lower()
        ]

    def tool_schema(self, server_id: str, tool_name: str) -> dict[str, Any]:
        """Return the input schema for a tool, cached after first fetch.

        Raises:
            KeyError: if no tool with that name exists on the server.
        """
        key = f"{server_id}:{tool_name}"
        cached = self._schema_cache.get(key)
        if cached is not None:
            return cached
        for tool in self.registry.tools_by_server(server_id):
            if tool.name == tool_name:
                self._schema_cache[key] = tool.input_schema
                return tool.input_schema
        raise KeyError(f"No tool '{tool_name}' on MCP server '{server_id}'")

    def compiled_list(self, server_id: str | None = None) -> list[dict[str, Any]]:
        """The compact registry view given to a model (name + description only).

        Keeps context small by deferring ``input_schema`` until a tool is used;
        the full schema is available via :meth:`tool_schema`.
        """
        return [
            {"server_id": t.server_id, "name": t.name, "description": t.description}
            for t in self.registry.tools_by_server(server_id)
        ]


class CodeExecutionTools:
    """Present MCP tools as filesystem-style code APIs.

    Lets an agent's code executor call an MCP tool by dotted name (e.g.
    ``tools.code_execute("filesystem.read_file", path=...)``) rather than fixing
    a binding per tool. Arguments are forwarded to the underlying server.
    """

    def __init__(self, manager: MCPManagerProto) -> None:
        self.manager = manager

    def resolve(self, dotted_name: str) -> tuple[str, str]:
        """Split a dotted name into ``(server_id, tool_name)``.

        Raises:
            ValueError: if the name is not ``server.tool``.
        """
        if "." not in dotted_name:
            raise ValueError(f"Expected 'server.tool' dotted name, got {dotted_name!r}")
        server_id, tool_name = dotted_name.rsplit(".", 1)
        return server_id, tool_name

    async def call(self, dotted_name: str, **arguments: Any) -> dict[str, Any]:
        """Invoke an MCP tool by dotted name with keyword arguments."""
        server_id, tool_name = self.resolve(dotted_name)
        return await self.manager.call_tool(server_id, tool_name, arguments)


class MCPServerManager:
    """Facade tying registry, search, and code execution to a client manager.

    This is the surface the architecture refers to as ``MCPServerManager``: it
    owns connection management (via ``MCPClientManager``) and exposes tool
    search/discovery through :class:`MCPRegistry` and :class:`MCPToolSearch`.
    """

    def __init__(self, client: MCPManagerProto | None = None) -> None:
        self.client = client or MCPClientManager()
        self.registry = MCPRegistry(self.client)
        self.search = MCPToolSearch(self.registry)
        self.code = CodeExecutionTools(self.client)

    async def connect_all(self) -> dict[str, bool]:
        """Connect all configured servers and refresh the tool/resource cache."""
        results = await self.client.connect_all()
        # Refresh caches from the (re)connected clients.
        self.registry.invalidate_tools()
        self.registry.invalidate_resources()
        return results

    async def disconnect_all(self) -> None:
        """Disconnect all servers and drop the caches."""
        await self.client.disconnect_all()
        self.registry.invalidate_tools()
        self.registry.invalidate_resources()

    def cache_tools_list(self) -> list[MCPTool]:
        """Forward to the registry's caching tool list (board contract)."""
        return self.registry.cache_tools_list()


__all__ = [
    "MCPManagerProto",
    "MCPRegistry",
    "MCPToolSearch",
    "CodeExecutionTools",
    "MCPServerManager",
]
