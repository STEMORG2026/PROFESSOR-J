"""Codex harness: HALF_OPEN probe must be allowed, not blocked."""

from __future__ import annotations

import time

from app.resources.circuit_breaker import CircuitBreaker, CircuitState


def test_codex_half_open_permits_probe() -> None:
    breaker = CircuitBreaker(name="codex-probe", failure_threshold=1, cooldown_seconds=0.001)
    breaker.record_failure()
    assert breaker.state.value == CircuitState.OPEN.value
    time.sleep(0.005)
    # Use value comparison to avoid mypy literal type issues
    assert breaker.state.value == CircuitState.HALF_OPEN.value
    # Independently discovered expectation: HALF_OPEN should allow call()
    breaker.call()
    breaker.record_success()
    assert breaker.state.value == CircuitState.CLOSED.value
