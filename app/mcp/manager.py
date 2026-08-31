"""MCP Server Manager - manages MCP server connections and tool discovery."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.domain.tool import SafetyTier
from app.exceptions import SafetyGateError
from app.guardrails.policy import SafetyPolicy
from app.mcp.transports import MCPMessage, MCPTransport, StdioTransport, StreamableHTTPTransport

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""

    name: str
    transport_type: str  # "stdio" or "http"
    command: list[str] | None = None
    url: str | None = None
    env: dict[str, str] | None = None
    headers: dict[str, str] | None = None
    enabled: bool = True


@dataclass
class MCPTool:
    """Represents an MCP tool. Carries a safety tier so external capability calls are gated."""

    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str
    # External MCP tools may have side effects; default to SENSITIVE (needs policy approval
    # check before execution). DESTRUCTIVE MCP tools would require HITL.
    tier: SafetyTier = field(default_factory=lambda: SafetyTier.SENSITIVE)


class MCPServerManager:
    """Manages multiple MCP server connections and tool discovery."""

    def __init__(self, policy: SafetyPolicy | None = None) -> None:
        self._servers: dict[str, MCPServerConfig] = {}
        self._transports: dict[str, MCPTransport] = {}
        self._tools: dict[str, MCPTool] = {}
        self._server_tools: dict[str, list[str]] = {}
        self._initialized = False
        # MCP is an EXTERNAL capability source: every tool call must be routed through the
        # safety gate (closes the audit's latent MCP bypass, ADVERSARIAL A4). Fail closed:
        # if no policy is wired, external tool execution is refused.
        self._policy = policy

    def register_server(self, config: MCPServerConfig) -> None:
        """Register an MCP server configuration."""
        if not config.enabled:
            return
        self._servers[config.name] = config
        if config.transport_type == "stdio":
            if not config.command:
                raise ValueError(f"Stdio server {config.name} requires command")
            self._transports[config.name] = StdioTransport(config.command, config.env)
        elif config.transport_type == "http":
            if not config.url:
                raise ValueError(f"HTTP server {config.name} requires url")
            self._transports[config.name] = StreamableHTTPTransport(config.url, config.headers)
        else:
            raise ValueError(f"Unknown transport type: {config.transport_type}")
        logger.info("Registered MCP server: %s (%s)", config.name, config.transport_type)

    async def initialize(self) -> None:
        """Initialize all registered servers and discover tools."""
        if self._initialized:
            return

        for name, transport in self._transports.items():
            try:
                await transport.connect()
                await self._discover_tools(name, transport)
            except Exception as e:
                logger.error("Failed to initialize MCP server %s: %s", name, e)
                # Continue with other servers

        self._initialized = True
        logger.info(
            "MCP Server Manager initialized with %d servers, %d tools",
            len(self._transports),
            len(self._tools),
        )

    async def _discover_tools(self, server_name: str, transport: MCPTransport) -> None:
        """Discover tools from an MCP server."""
        # Send tools/list request
        request = MCPMessage(id=1, method="tools/list", params={})
        await transport.send(request)

        # Wait for response
        response = await transport.receive()
        if response and response.result and "tools" in response.result:
            tools_data = response.result["tools"]
            self._server_tools[server_name] = []
            for tool_data in tools_data:
                tool = MCPTool(
                    name=tool_data["name"],
                    description=tool_data.get("description", ""),
                    input_schema=tool_data.get("inputSchema", {}),
                    server_name=server_name,
                )
                self._tools[tool.name] = tool
                self._server_tools[server_name].append(tool.name)
            logger.info("Discovered %d tools from MCP server %s", len(tools_data), server_name)

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Call an MCP tool by name, routed through the safety gate (fail closed)."""
        tool = self._tools.get(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")

        # Security boundary: an external (MCP) capability must NOT execute without passing
        # the safety policy. Fail closed — refuse if no gate is wired. Closes the audit's
        # latent MCP bypass (ADVERSARIAL A4: external tool call avoiding @safety_gate).
        if self._policy is None:
            raise SafetyGateError(
                tool=tool_name,
                tier=tool.tier.value,
                reason=(
                    "MCP tool call refused: no safety policy wired "
                    "(external capability must be gated)"
                ),
            )
        self._policy.check(tool_name, arguments, tool.tier, tool.description)

        transport = self._transports.get(tool.server_name)
        if not transport or not transport.is_connected:
            raise RuntimeError(f"Server {tool.server_name} not connected")

        # Send tools/call request
        request = MCPMessage(
            id=2, method="tools/call", params={"name": tool_name, "arguments": arguments}
        )
        await transport.send(request)

        # Wait for response
        response = await transport.receive()
        if response and response.result:
            return response.result
        if response and response.error:
            raise RuntimeError(f"MCP tool error: {response.error}")
        raise RuntimeError("No response from MCP tool call")

    def list_tools(self) -> list[MCPTool]:
        """List all available tools."""
        return list(self._tools.values())

    def get_tool(self, tool_name: str) -> MCPTool | None:
        """Get a tool by name."""
        return self._tools.get(tool_name)

    def get_server_tools(self, server_name: str) -> list[MCPTool]:
        """Get all tools for a specific server."""
        tool_names = self._server_tools.get(server_name, [])
        return [self._tools[name] for name in tool_names if name in self._tools]

    async def shutdown(self) -> None:
        """Shutdown all server connections."""
        for name, transport in self._transports.items():
            try:
                await transport.disconnect()
            except Exception as e:
                logger.warning("Error disconnecting MCP server %s: %s", name, e)
        self._transports.clear()
        self._tools.clear()
        self._server_tools.clear()
        self._initialized = False
        logger.info("MCP Server Manager shut down")
