"""Timezone-aware time helpers for the pure domain layer."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime.

    Replaces the deprecated ``datetime.utcnow()`` (which returns a naive
    timestamp). Domain dataclasses default to aware UTC so serialization that
    emits ISO-8601 includes the offset, and cross-source comparisons are safe.
    """
    return datetime.now(UTC)
