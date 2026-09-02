"""MCP (Model Context Protocol) subsystem.

The subsystem deliberately hosts **two separate MCP layers** (see the
MCP architecture decision):

1. ``app.mcp.client`` — the restored **protocol/client layer**
   (``StdioMCPClient``, ``SSEClient``, ``MCPClientManager``, ``MCPToolSkill``,
   ``create_mcp_manager_from_config``) using ``MCPTool.server_id`` /
   ``MCPServerConfig.transport``. This is exported from the package namespace
   to satisfy existing imports (``tests/unit/mcp/test_client.py``,
   ``tests/unit/mcp/test_registry.py``, ``tests/unit/skills``, ``app/skills``).

2. ``app.mcp.manager`` + ``app.mcp.search`` + ``app.mcp.transports`` — the
   current **management/configuration layer** (``MCPServerManager``,
   ``MCPServerConfig.transport_type``/``headers``, ``MCPTool.server_name``).
   This is intentionally NOT re-exported here to avoid ambiguous package-level
   names; import it explicitly via its submodules
   (``from app.mcp.manager import MCPTool``).

These layers have distinct, currently-incompatible domain models. Their side-by-side
existence is deliberate and documented; final unification is a separate future
architectural decision. Do NOT treat ``app.mcp.MCPTool`` and
``app.mcp.manager.MCPTool`` as interchangeable.
"""

from app.mcp.client import (
    MCPClientBase,
    MCPClientManager,
    MCPResource,
    MCPServerConfig,
    MCPTool,
    MCPToolSkill,
    SSEClient,
    StdioMCPClient,
    create_mcp_manager_from_config,
)

__all__ = [
    "MCPClientBase",
    "MCPClientManager",
    "MCPResource",
    "MCPServerConfig",
    "MCPTool",
    "MCPToolSkill",
    "SSEClient",
    "StdioMCPClient",
    "create_mcp_manager_from_config",
]
