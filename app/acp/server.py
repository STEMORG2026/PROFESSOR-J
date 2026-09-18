"""Agent Client Protocol (ACP) Server for PROFESSOR-J.

Implements a JSON-RPC 2.0 server that allows other agents to connect
to PROFESSOR-J and invoke orchestration capabilities.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ACPRequest:
    """ACP JSON-RPC 2.0 request."""

    jsonrpc: str = "2.0"
    id: str | None = None
    method: str = ""
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ACPResponse:
    """ACP JSON-RPC 2.0 response."""

    jsonrpc: str = "2.0"
    id: str | None = None
    result: Any = None
    error: dict[str, Any] | None = None


class ACPServer:
    """Agent Client Protocol JSON-RPC server.

    Accepts connections from external agents (dsh, Hermes, OpenCode)
    and dispatches method calls to registered handlers.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, Any] = {}

    def register_method(self, name: str, handler: Any) -> None:
        """Register an ACP method handler."""
        self._handlers[name] = handler

    async def handle_request(self, request: ACPRequest) -> ACPResponse:
        """Handle an incoming ACP request."""
        if request.method not in self._handlers:
            return ACPResponse(
                id=request.id,
                error={"code": -32601, "message": f"Method not found: {request.method}"},
            )

        handler = self._handlers[request.method]
        try:
            result = await handler(request.params)
            return ACPResponse(id=request.id, result=result)
        except Exception as exc:  # noqa: BLE001
            return ACPResponse(
                id=request.id,
                error={"code": -32603, "message": str(exc)},
            )

    async def handle_message(self, message: str) -> str:
        """Handle a raw JSON-RPC message and return the response."""
        try:
            data = json.loads(message)
            request = ACPRequest(**data)
            response = await self.handle_request(request)
            return json.dumps(response.__dict__)
        except json.JSONDecodeError:
            return json.dumps(
                {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}}
            )


# ── Built-in ACP Methods ───────────────────────────────────────────────


async def status_method(_params: dict[str, Any]) -> dict[str, str]:
    """Return server status."""
    return {"status": "ready", "protocol": "acp/1.0"}


async def capabilities_method(_params: dict[str, Any]) -> dict[str, Any]:
    """Return server capabilities."""
    return {
        "methods": ["status", "capabilities", "spawn", "control", "route"],
        "orchestration": ["subagent", "plugin", "hook"],
    }


def create_acp_server() -> ACPServer:
    """Create and configure the ACP server."""
    server = ACPServer()
    server.register_method("status", status_method)
    server.register_method("capabilities", capabilities_method)
    return server


__all__ = ["ACPServer", "ACPRequest", "ACPResponse", "create_acp_server"]
