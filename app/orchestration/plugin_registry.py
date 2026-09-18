"""Plugin Registry — runtime capability discovery."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PluginCapability:
    """A registered plugin capability."""

    name: str
    description: str
    handler: Callable[..., Any]
    metadata: dict[str, Any] = field(default_factory=dict)


class PluginRegistry:
    """Runtime capability discovery for orchestration plugins."""

    def __init__(self) -> None:
        self._plugins: dict[str, PluginCapability] = {}

    def register(
        self,
        name: str,
        description: str,
        handler: Callable[..., Any],
        **metadata: Any,
    ) -> None:
        """Register a plugin capability."""
        self._plugins[name] = PluginCapability(
            name=name,
            description=description,
            handler=handler,
            metadata=metadata,
        )
        logger.info("Registered plugin: %s", name)

    def get(self, name: str) -> PluginCapability | None:
        """Get a plugin by name."""
        return self._plugins.get(name)

    def list_plugins(self) -> list[PluginCapability]:
        """List all registered plugins."""
        return list(self._plugins.values())

    def discover(self, query: str) -> list[PluginCapability]:
        """Discover plugins matching a query."""
        query_lower = query.lower()
        return [
            p
            for p in self._plugins.values()
            if query_lower in p.name.lower() or query_lower in p.description.lower()
        ]


def create_plugin_registry() -> PluginRegistry:
    """Create a plugin registry."""
    return PluginRegistry()


__all__ = ["PluginRegistry", "PluginCapability", "create_plugin_registry"]
