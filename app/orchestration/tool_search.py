"""Tool Search — find tools across connected agents.

Modeled on dsh `tool-skill`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ToolInfo:
    """Information about a tool."""

    name: str
    description: str
    agent: str  # which agent provides this tool
    capability: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolSearch:
    """Search tools across connected agents."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolInfo] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        agent: str,
        capability: str,
        **metadata: Any,
    ) -> None:
        """Register a tool from an agent."""
        self._tools[name] = ToolInfo(
            name=name,
            description=description,
            agent=agent,
            capability=capability,
            metadata=metadata,
        )
        logger.info("Registered tool: %s from agent: %s", name, agent)

    def search(self, query: str) -> list[ToolInfo]:
        """Search for tools matching a query."""
        query_lower = query.lower()
        return [
            t
            for t in self._tools.values()
            if query_lower in t.name.lower() or query_lower in t.description.lower()
        ]

    def list_agent_tools(self, agent: str) -> list[ToolInfo]:
        """List tools from a specific agent."""
        return [t for t in self._tools.values() if t.agent == agent]

    def list_all_tools(self) -> list[ToolInfo]:
        """List all registered tools."""
        return list(self._tools.values())


def create_tool_search() -> ToolSearch:
    """Create a tool search."""
    return ToolSearch()


__all__ = ["ToolSearch", "ToolInfo", "create_tool_search"]
