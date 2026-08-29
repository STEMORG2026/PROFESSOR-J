"""MCP (Model Context Protocol) client integration for PROFESSOR-J.

This module provides:
- MCP server connection management
- Tool discovery and invocation from MCP servers
- Resource access from MCP servers
- Integration with the skill system
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MCPTool:
    """Represents a tool provided by an MCP server."""

    name: str
    description: str
    input_schema: dict[str, Any]
    server_id: str


@dataclass(frozen=True, slots=True)
class MCPResource:
    """Represents a resource provided by an MCP server."""

    uri: str
    name: str
    description: str | None
    mime_type: str | None
    server_id: str


@dataclass(frozen=True, slots=True)
class MCPServerConfig:
    """Configuration for an MCP server connection."""

    server_id: str
    name: str
    transport: str  # "stdio", "sse", "websocket"
    command: list[str] | None = None  # For stdio transport
    args: list[str] | None = None  # For stdio transport
    url: str | None = None  # For SSE/WebSocket transport
    env: dict[str, str] | None = None  # Environment variables
    timeout_seconds: int = 30
    auto_reconnect: bool = True


class MCPClientBase(ABC):
    """Abstract base class for MCP transport clients."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the MCP server."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the MCP server."""

    @abstractmethod
    async def initialize(self) -> dict[str, Any]:
        """Send initialize request and return server capabilities."""

    @abstractmethod
    async def list_tools(self) -> list[MCPTool]:
        """List available tools from the server."""

    @abstractmethod
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool on the server."""

    @abstractmethod
    async def list_resources(self) -> list[MCPResource]:
        """List available resources from the server."""

    @abstractmethod
    async def read_resource(self, uri: str) -> dict[str, Any]:
        """Read a resource from the server."""

    @abstractmethod
    async def subscribe_resource(self, uri: str) -> None:
        """Subscribe to resource updates."""

    @abstractmethod
    async def unsubscribe_resource(self, uri: str) -> None:
        """Unsubscribe from resource updates."""


class StdioMCPClient(MCPClientBase):
    """MCP client using stdio transport (subprocess)."""

    def __init__(self, config: MCPServerConfig) -> None:
        if not config.command:
            raise ValueError("stdio transport requires 'command' in config")
        self.config = config
        self._process: asyncio.subprocess.Process | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._request_id = 0
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._initialized = False
        self._server_info: dict[str, Any] = {}
        self._capabilities: dict[str, Any] = {}

    async def connect(self) -> None:
        """Launch the subprocess and establish stdio communication."""
        env = os.environ.copy()
        if self.config.env:
            env.update(self.config.env)

        self._process = await asyncio.create_subprocess_exec(
            *(self.config.command or []),
            *(self.config.args or []),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        self._reader = self._process.stdout
        self._writer = self._process.stdin

        # Start message reader task
        asyncio.create_task(self._read_messages())

        # Initialize
        await self.initialize()

    async def disconnect(self) -> None:
        """Terminate the subprocess."""
        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except TimeoutError:
                self._process.kill()
                await self._process.wait()
            self._process = None

    async def _read_messages(self) -> None:
        """Read JSON-RPC messages from stdout."""
        if not self._reader:
            return

        buffer = ""
        while self._process and self._reader and not self._reader.at_eof():
            try:
                line = await self._reader.readline()
                if not line:
                    break
                buffer += line.decode("utf-8")

                # Try to parse complete JSON messages
                while buffer.strip():
                    try:
                        msg, consumed = self._try_parse_json(buffer)
                        if msg:
                            buffer = buffer[consumed:]
                            self._handle_message(msg)
                        else:
                            break
                    except json.JSONDecodeError:
                        break
            except Exception as e:
                logger.error("Error reading MCP messages: %s", e)
                break

    def _try_parse_json(self, buffer: str) -> tuple[dict[str, Any] | None, int]:
        """Try to parse a JSON message from buffer. Returns (message, consumed_chars)."""
        buffer = buffer.strip()
        if not buffer:
            return None, 0

        try:
            # Find the end of the JSON object
            depth = 0
            in_string = False
            escape = False
            for i, ch in enumerate(buffer):
                if escape:
                    escape = False
                    continue
                if ch == "\\":
                    escape = True
                    continue
                if ch == '"' and not escape:
                    in_string = not in_string
                    continue
                if not in_string:
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            msg = json.loads(buffer[: i + 1])
                            return msg, i + 1
        except json.JSONDecodeError:
            pass
        return None, 0

    def _handle_message(self, msg: dict[str, Any]) -> None:
        """Handle incoming JSON-RPC message."""
        if "id" in msg and msg["id"] in self._pending:
            # Response to our request
            future = self._pending.pop(msg["id"])
            if "error" in msg:
                future.set_exception(Exception(msg["error"].get("message", "Unknown error")))
            else:
                future.set_result(msg.get("result"))
        elif "method" in msg:
            # Notification or request from server
            self._handle_notification(msg)

    def _handle_notification(self, msg: dict[str, Any]) -> None:
        """Handle server notifications."""
        method = msg.get("method")
        logger.debug("MCP notification: %s", method)

    async def _send_request(
        self, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send a JSON-RPC request and wait for response."""
        if not self._writer:
            raise RuntimeError("Not connected")

        self._request_id += 1
        request_id = self._request_id

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
        }

        future: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
        self._pending[request_id] = future

        data = json.dumps(request) + "\n"
        self._writer.write(data.encode("utf-8"))
        await self._writer.drain()

        try:
            return await asyncio.wait_for(future, timeout=self.config.timeout_seconds)
        except TimeoutError:
            self._pending.pop(request_id, None)
            raise TimeoutError(f"MCP request {method} timed out") from None

    async def initialize(self) -> dict[str, Any]:
        """Initialize the MCP connection."""
        if self._initialized:
            return self._server_info

        result = await self._send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {},
                },
                "clientInfo": {
                    "name": "PROFESSOR-J",
                    "version": "0.1.0",
                },
            },
        )

        self._server_info = result.get("serverInfo", {})
        self._capabilities = result.get("capabilities", {})
        self._initialized = True

        # Send initialized notification
        await self._send_notification("notifications/initialized", {})

        return self._server_info

    async def _send_notification(self, method: str, params: dict[str, Any] | None = None) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        if not self._writer:
            raise RuntimeError("Not connected")

        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
        }

        data = json.dumps(notification) + "\n"
        self._writer.write(data.encode("utf-8"))
        await self._writer.drain()

    async def list_tools(self) -> list[MCPTool]:
        """List available tools from the server."""
        result = await self._send_request("tools/list")
        tools = []
        for tool_data in result.get("tools", []):
            tools.append(
                MCPTool(
                    name=tool_data["name"],
                    description=tool_data.get("description", ""),
                    input_schema=tool_data.get("inputSchema", {}),
                    server_id=self.config.server_id,
                )
            )
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool on the server."""
        result = await self._send_request(
            "tools/call",
            {
                "name": name,
                "arguments": arguments,
            },
        )
        return result

    async def list_resources(self) -> list[MCPResource]:
        """List available resources from the server."""
        result = await self._send_request("resources/list")
        resources = []
        for res_data in result.get("resources", []):
            resources.append(
                MCPResource(
                    uri=res_data["uri"],
                    name=res_data.get("name", ""),
                    description=res_data.get("description"),
                    mime_type=res_data.get("mimeType"),
                    server_id=self.config.server_id,
                )
            )
        return resources

    async def read_resource(self, uri: str) -> dict[str, Any]:
        """Read a resource from the server."""
        result = await self._send_request("resources/read", {"uri": uri})
        return result

    async def subscribe_resource(self, uri: str) -> None:
        """Subscribe to resource updates."""
        await self._send_request("resources/subscribe", {"uri": uri})

    async def unsubscribe_resource(self, uri: str) -> None:
        """Unsubscribe from resource updates."""
        await self._send_request("resources/unsubscribe", {"uri": uri})


class SSEClient(MCPClientBase):
    """MCP client using Server-Sent Events transport (placeholder for future implementation)."""

    def __init__(self, config: MCPServerConfig) -> None:
        if not config.url:
            raise ValueError("SSE transport requires 'url' in config")
        self.config = config
        raise NotImplementedError("SSE transport not yet implemented")

    async def connect(self) -> None:
        raise NotImplementedError

    async def disconnect(self) -> None:
        raise NotImplementedError

    async def initialize(self) -> dict[str, Any]:
        raise NotImplementedError

    async def list_tools(self) -> list[MCPTool]:
        raise NotImplementedError

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    async def list_resources(self) -> list[MCPResource]:
        raise NotImplementedError

    async def read_resource(self, uri: str) -> dict[str, Any]:
        raise NotImplementedError

    async def subscribe_resource(self, uri: str) -> None:
        raise NotImplementedError

    async def unsubscribe_resource(self, uri: str) -> None:
        raise NotImplementedError


class MCPClientManager:
    """Manages multiple MCP server connections."""

    def __init__(self) -> None:
        self._clients: dict[str, MCPClientBase] = {}
        self._configs: dict[str, MCPServerConfig] = {}
        self._all_tools: dict[str, MCPTool] = {}
        self._all_resources: dict[str, MCPResource] = {}

    def add_server(self, config: MCPServerConfig) -> None:
        """Add an MCP server configuration."""
        self._configs[config.server_id] = config

        client: MCPClientBase
        if config.transport == "stdio":
            client = StdioMCPClient(config)
        elif config.transport == "sse":
            client = SSEClient(config)
        else:
            raise ValueError(f"Unsupported transport: {config.transport}")

        self._clients[config.server_id] = client

    async def connect_all(self) -> dict[str, bool]:
        """Connect to all configured servers. Returns connection status."""
        results = {}
        for server_id, client in self._clients.items():
            try:
                await client.connect()
                # Refresh tools and resources
                await self._refresh_server(server_id)
                results[server_id] = True
                logger.info("Connected to MCP server: %s", server_id)
            except Exception as e:
                logger.error("Failed to connect to MCP server %s: %s", server_id, e)
                results[server_id] = False
        return results

    async def _refresh_server(self, server_id: str) -> None:
        """Refresh tools and resources for a server."""
        client = self._clients.get(server_id)
        if not client:
            return

        try:
            tools = await client.list_tools()
            for tool in tools:
                self._all_tools[f"{server_id}:{tool.name}"] = tool

            resources = await client.list_resources()
            for res in resources:
                self._all_resources[f"{server_id}:{res.uri}"] = res
        except Exception as e:
            logger.error("Failed to refresh server %s: %s", server_id, e)

    async def disconnect_all(self) -> None:
        """Disconnect from all servers."""
        for server_id, client in self._clients.items():
            try:
                await client.disconnect()
            except Exception as e:
                logger.error("Error disconnecting from %s: %s", server_id, e)
        self._clients.clear()
        self._all_tools.clear()
        self._all_resources.clear()

    def get_tool(self, tool_key: str) -> MCPTool | None:
        """Get a tool by its key (server_id:tool_name)."""
        return self._all_tools.get(tool_key)

    def list_tools(self) -> list[MCPTool]:
        """List all available tools from all connected servers."""
        return list(self._all_tools.values())

    def get_resource(self, resource_key: str) -> MCPResource | None:
        """Get a resource by its key (server_id:uri)."""
        return self._all_resources.get(resource_key)

    def list_resources(self) -> list[MCPResource]:
        """List all available resources from all connected servers."""
        return list(self._all_resources.values())

    async def call_tool(
        self, server_id: str, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Call a tool on a specific server."""
        client = self._clients.get(server_id)
        if not client:
            raise ValueError(f"Server not found: {server_id}")
        return await client.call_tool(tool_name, arguments)

    async def read_resource(self, server_id: str, uri: str) -> dict[str, Any]:
        """Read a resource from a specific server."""
        client = self._clients.get(server_id)
        if not client:
            raise ValueError(f"Server not found: {server_id}")
        return await client.read_resource(uri)


class MCPToolSkill:
    """Skill that wraps MCP tools for use in the skill system."""

    def __init__(self, mcp_manager: MCPClientManager) -> None:
        self._mcp_manager = mcp_manager

    async def execute_tool(
        self, server_id: str, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute an MCP tool."""
        return await self._mcp_manager.call_tool(server_id, tool_name, arguments)

    async def read_resource(self, server_id: str, uri: str) -> dict[str, Any]:
        """Read an MCP resource."""
        return await self._mcp_manager.read_resource(server_id, uri)

    def list_available_tools(self) -> list[dict[str, Any]]:
        """List all available MCP tools."""
        tools = self._mcp_manager.list_tools()
        return [
            {
                "key": f"{t.server_id}:{t.name}",
                "name": t.name,
                "description": t.description,
                "server_id": t.server_id,
                "input_schema": t.input_schema,
            }
            for t in tools
        ]

    def list_available_resources(self) -> list[dict[str, Any]]:
        """List all available MCP resources."""
        resources = self._mcp_manager.list_resources()
        return [
            {
                "key": f"{r.server_id}:{r.uri}",
                "uri": r.uri,
                "name": r.name,
                "description": r.description,
                "mime_type": r.mime_type,
                "server_id": r.server_id,
            }
            for r in resources
        ]


def create_mcp_manager_from_config(config_path: str = "mcp_servers.json") -> MCPClientManager:
    """Create an MCPClientManager from a JSON config file."""
    manager = MCPClientManager()

    if not os.path.exists(config_path):
        logger.warning("MCP config file not found: %s", config_path)
        return manager

    try:
        with open(config_path) as f:
            config_data = json.load(f)
    except Exception as e:
        logger.error("Failed to load MCP config: %s", e)
        return manager

    for server_data in config_data.get("servers", []):
        config = MCPServerConfig(
            server_id=server_data["server_id"],
            name=server_data["name"],
            transport=server_data["transport"],
            command=server_data.get("command"),
            args=server_data.get("args"),
            url=server_data.get("url"),
            env=server_data.get("env"),
            timeout_seconds=server_data.get("timeout_seconds", 30),
            auto_reconnect=server_data.get("auto_reconnect", True),
        )
        manager.add_server(config)

    return manager


__all__ = [
    "MCPTool",
    "MCPResource",
    "MCPServerConfig",
    "MCPClientBase",
    "StdioMCPClient",
    "SSEClient",
    "MCPClientManager",
    "MCPToolSkill",
    "create_mcp_manager_from_config",
]
