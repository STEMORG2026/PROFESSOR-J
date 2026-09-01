"""Strongly-typed event contracts for passive cross-cutting concerns.

Used exclusively by :class:`~app.events.bus.InMemoryAsyncBus` for telemetry,
logging, metrics, background jobs, streaming events, and scheduler notifications.
Core execution loops MUST use direct async interface calls instead of the bus
(pattern inherited from JARVIS ``app/events/models.py``).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.domain.tool import SafetyTier


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Event:
    """Base event contract."""

    event_type: str
    event_id: str = ""
    timestamp: datetime = field(default_factory=_utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict (timestamps as ISO strings)."""
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        return payload


@dataclass
class TelemetryEvent(Event):
    """Telemetry / tracing / metric event."""

    event_type: str = "telemetry"
    category: str = "telemetry"
    component: str = "system"
    duration_ms: float | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepExecutionEvent(Event):
    """Emitted during cognitive-engine step transitions."""

    event_type: str = "step.execution"
    plan_id: str = ""
    step_id: str = ""
    title: str = ""
    status: str = "pending"
    result: Any | None = None
    error: str | None = None


@dataclass
class HITLRequestEvent(Event):
    """Emitted when a DESTRUCTIVE step requires human-in-the-loop approval."""

    event_type: str = "hitl.request"
    plan_id: str = ""
    step_id: str = ""
    title: str = ""
    tool_name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    safety_tier: SafetyTier = SafetyTier.DESTRUCTIVE


@dataclass
class ToolExecutionEvent(Event):
    """Emitted around a tool-execution (start/end), for telemetry + audit."""

    event_type: str = "tool.execution"
    tool_name: str = ""
    status: str = "started"
    duration_ms: float | None = None
    error: str | None = None


__all__ = [
    "Event",
    "TelemetryEvent",
    "StepExecutionEvent",
    "HITLRequestEvent",
    "ToolExecutionEvent",
]
