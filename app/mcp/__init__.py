"""MCP (Model Context Protocol) client subsystem.

Phase 1 deliverable: MCPServerManager interface, stdio + Streamable HTTP transports,
MCPToolSearch for on-demand loading, MCPRegistry for caching.
"""

from app.mcp.manager import MCPServerManager
from app.mcp.registry import MCPRegistry
from app.mcp.search import MCPToolSearch
from app.mcp.transports import StdioTransport, StreamableHTTPTransport

__all__ = [
    "MCPServerManager",
    "MCPRegistry",
    "MCPToolSearch",
    "StdioTransport",
    "StreamableHTTPTransport",
]
