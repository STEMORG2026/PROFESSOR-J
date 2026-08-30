"""MCP Registry - caching and persistence for MCP server configurations and tools."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path

from app.mcp.manager import MCPServerConfig, MCPTool

logger = logging.getLogger(__name__)


class MCPRegistry:
    """Registry for MCP server configurations and discovered tools.

    Provides caching so tool discovery doesn't need to run on every startup.
    """

    def __init__(self, cache_path: str | Path | None = None) -> None:
        self._cache_path = Path(cache_path) if cache_path else None
        self._server_configs: dict[str, MCPServerConfig] = {}
        self._tools: dict[str, MCPTool] = {}
        self._server_tools: dict[str, list[str]] = {}

    def register_server(self, config: MCPServerConfig) -> None:
        """Register a server configuration."""
        self._server_configs[config.name] = config

    def get_server_config(self, name: str) -> MCPServerConfig | None:
        """Get a server configuration by name."""
        return self._server_configs.get(name)

    def list_server_configs(self) -> list[MCPServerConfig]:
        """List all server configurations."""
        return list(self._server_configs.values())

    def remove_server(self, name: str) -> bool:
        """Remove a server configuration."""
        if name in self._server_configs:
            del self._server_configs[name]
            return True
        return False

    def cache_tools(self, server_name: str, tools: list[MCPTool]) -> None:
        """Cache discovered tools for a server."""
        self._server_tools[server_name] = [tool.name for tool in tools]
        for tool in tools:
            self._tools[tool.name] = tool

    def cache_tools_list(self, server_name: str, tool_names: list[str]) -> None:
        """Cache a list of tool names for a server (lazy loading)."""
        self._server_tools[server_name] = tool_names

    def get_cached_tools(self, server_name: str) -> list[MCPTool]:
        """Get cached tools for a server."""
        tool_names = self._server_tools.get(server_name, [])
        return [self._tools[name] for name in tool_names if name in self._tools]

    def get_all_cached_tools(self) -> list[MCPTool]:
        """Get all cached tools."""
        return list(self._tools.values())

    def has_cached_tools(self, server_name: str) -> bool:
        """Check if tools are cached for a server."""
        return server_name in self._server_tools

    def clear_cache(self, server_name: str | None = None) -> None:
        """Clear cached tools for a server or all servers."""
        if server_name:
            if server_name in self._server_tools:
                for tool_name in self._server_tools[server_name]:
                    self._tools.pop(tool_name, None)
                del self._server_tools[server_name]
        else:
            self._tools.clear()
            self._server_tools.clear()

    def save(self) -> None:
        """Save registry to cache file."""
        if not self._cache_path:
            return
        try:
            data = {
                "servers": {name: asdict(config) for name, config in self._server_configs.items()},
                "tools": {name: asdict(tool) for name, tool in self._tools.items()},
                "server_tools": self._server_tools,
            }
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            logger.info("MCP registry saved to %s", self._cache_path)
        except Exception as e:
            logger.warning("Failed to save MCP registry: %s", e)

    def load(self) -> bool:
        """Load registry from cache file. Returns True if loaded successfully."""
        if not self._cache_path or not self._cache_path.exists():
            return False
        try:
            data = json.loads(self._cache_path.read_text(encoding="utf-8"))
            for name, config_data in data.get("servers", {}).items():
                self._server_configs[name] = MCPServerConfig(**config_data)
            for name, tool_data in data.get("tools", {}).items():
                self._tools[name] = MCPTool(**tool_data)
            self._server_tools = data.get("server_tools", {})
            logger.info(
                "MCP registry loaded from %s: %d servers, %d tools",
                self._cache_path,
                len(self._server_configs),
                len(self._tools),
            )
            return True
        except Exception as e:
            logger.warning("Failed to load MCP registry: %s", e)
            return False
