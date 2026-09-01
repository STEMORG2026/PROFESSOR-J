"""In-memory async event bus — decoupled passive telemetry.

Pattern-inherited from JARVIS ``app/events/bus.py``.

Reserved for *passive* cross-cutting concerns: telemetry, logging, metrics,
background jobs, streaming events, and scheduler notifications. Core execution
loops MUST use direct async interface calls instead of the bus — publishing via
the bus is fire-and-forget telemetry, never the data path.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from app.events.models import Event

logger = logging.getLogger(__name__)

E = TypeVar("E", bound=Event)
EventHandler = Callable[[E], Awaitable[None]]


class InMemoryAsyncBus:
    """Decoupled in-memory asynchronous pub/sub for passive telemetry."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler[Any]]] = {}

    def subscribe(self, event_type: str, handler: EventHandler[Any]) -> None:
        """Register an async handler for an event-type string (or ``*`` for all)."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)
            logger.debug("Subscribed %s to %s", handler.__name__, event_type)

    def unsubscribe(self, event_type: str, handler: EventHandler[Any]) -> None:
        if event_type in self._handlers and handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

    async def publish_async(self, event: Event) -> None:
        """Publish an event, awaiting all (matching + wildcard) handlers concurrently.

        Handler exceptions are caught and logged so a bad subscriber can never
        break the publisher.
        """
        handlers = self._handlers.get(event.event_type, []) + self._handlers.get("*", [])
        if not handlers:
            return
        await asyncio.gather(
            *(self._safe_execute(h, event) for h in handlers), return_exceptions=True
        )

    def publish(self, event: Event) -> None:
        """Fire-and-forget dispatch via a background task (passive telemetry)."""
        if not event.event_id:
            import uuid

            event.event_id = uuid.uuid4().hex[:12]
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.publish_async(event))
        except RuntimeError:
            logger.warning("No running asyncio event loop for event %s", event.event_type)

    async def _safe_execute(self, handler: EventHandler[Any], event: Event) -> None:
        try:
            await handler(event)
        except Exception as err:  # noqa: BLE001 - a bad subscriber must not propagate
            logger.exception(
                "Event handler %s failed for %s: %s", handler.__name__, event.event_id, err
            )


__all__ = ["InMemoryAsyncBus", "EventHandler"]
