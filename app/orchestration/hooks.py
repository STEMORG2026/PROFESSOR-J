"""Hooks System — Claude Code + Codex bridge protocol.

Provides a standardized wire protocol for agent-to-agent hooks
(modeled on dsh `hooks/` packages).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class HookEvent:
    """A hook lifecycle event."""

    event_type: str  # session_start, task_complete, error, agent_spawn, agent_stop
    payload: dict[str, Any] = field(default_factory=dict)
    source: str = ""


@dataclass
class HookResult:
    """Result of a hook execution."""

    success: bool
    action: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class HooksSystem:
    """Manages agent-to-agent hooks."""

    def __init__(self) -> None:
        self._hooks: dict[str, list[Callable[..., Any]]] = {}

    def register_hook(self, event_type: str, handler: Callable[..., Any]) -> None:
        """Register a hook handler for an event type."""
        if event_type not in self._hooks:
            self._hooks[event_type] = []
        self._hooks[event_type].append(handler)
        logger.info("Registered hook: %s", event_type)

    async def fire_hook(self, event: HookEvent) -> list[HookResult]:
        """Fire all hooks for an event type."""
        results = []
        handlers = self._hooks.get(event.event_type, [])
        for handler in handlers:
            try:
                result = await handler(event)
                results.append(result)
            except Exception as exc:  # noqa: BLE001
                logger.error("Hook failed for %s: %s", event.event_type, exc)
                results.append(HookResult(success=False, action="error"))
        return results


def create_hooks_system() -> HooksSystem:
    """Create a hooks system."""
    return HooksSystem()


__all__ = ["HooksSystem", "HookEvent", "HookResult", "create_hooks_system"]
