"""Passive event bus — decoupled cross-cutting telemetry (JARVIS parity).

The bus is reserved for telemetry/logging/metrics/background jobs, NOT the core
data path. Core execution loops call services directly.
"""

from app.events.bus import EventHandler, InMemoryAsyncBus
from app.events.models import (
    Event,
    HITLRequestEvent,
    StepExecutionEvent,
    TelemetryEvent,
    ToolExecutionEvent,
)

__all__ = [
    "InMemoryAsyncBus",
    "EventHandler",
    "Event",
    "TelemetryEvent",
    "StepExecutionEvent",
    "HITLRequestEvent",
    "ToolExecutionEvent",
]
