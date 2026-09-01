"""Three-state circuit breaker for LLM provider failover.

States: ``CLOSED`` (normal), ``OPEN`` (rejecting), ``HALF_OPEN`` (probing
recovery). On repeated failures the breaker opens; after a cooldown it moves to
half-open and allows a single probe call; success closes it, failure reopens it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum

from app.exceptions import CircuitOpenError


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(slots=True)
class CircuitBreaker:
    """A per-provider circuit breaker with fixed threshold and cooldown."""

    name: str
    failure_threshold: int = 5
    cooldown_seconds: float = 30.0
    _state: CircuitState = CircuitState.CLOSED
    _failure_count: int = 0
    _opened_at: float | None = None

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN and self._cooldown_elapsed():
            self._state = CircuitState.HALF_OPEN
        return self._state

    def call(self) -> None:
        """Called before a request. Raises if the circuit is not accepting.

        HALF_OPEN allows a single probe — the breaker remains half-open until
        record_success or record_failure determines the outcome.
        """
        state = self.state
        if state == CircuitState.OPEN:
            raise CircuitOpenError(provider=self.name, opened_at=self._opened_at or time.time())

    def record_success(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
        self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call; open the circuit once the threshold is hit."""
        self._failure_count += 1
        if self._state == CircuitState.HALF_OPEN:
            # A probe failure reopens immediately.
            self._open()
            return
        if self._failure_count >= self.failure_threshold:
            self._open()

    def reset(self) -> None:
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at = None

    def _open(self) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = time.time()

    def _cooldown_elapsed(self) -> bool:
        return bool(
            self._opened_at is not None and (time.time() - self._opened_at) >= self.cooldown_seconds
        )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"CircuitBreaker(name={self.name!r}, "
            f"state={self.state.value!r}, "
            f"failures={self._failure_count})"
        )
