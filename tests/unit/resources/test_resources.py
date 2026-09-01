"""Tests for circuit breaker and token budget."""

from __future__ import annotations

import time

import pytest

from app.exceptions import CircuitOpenError
from app.resources.budget import TokenBudget
from app.resources.circuit_breaker import CircuitBreaker, CircuitState


class TestCircuitBreaker:
    def test_starts_closed(self) -> None:
        breaker = CircuitBreaker(name="p1")
        assert breaker.state == CircuitState.CLOSED

    def test_opens_after_threshold_failures(self) -> None:
        breaker = CircuitBreaker(name="p1", failure_threshold=2)
        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN  # type: ignore[comparison-overlap]

    def test_call_raises_when_open(self) -> None:
        breaker = CircuitBreaker(name="p1", failure_threshold=1, cooldown_seconds=999)
        breaker.record_failure()
        with pytest.raises(CircuitOpenError):
            breaker.call()

    def test_success_resets_failures(self) -> None:
        breaker = CircuitBreaker(name="p1", failure_threshold=3)
        breaker.record_failure()
        breaker.record_success()
        assert breaker._failure_count == 0
        assert breaker.state == CircuitState.CLOSED

    def test_half_open_probe_failure_reopens(self, monkeypatch: pytest.MonkeyPatch) -> None:
        breaker = CircuitBreaker(name="p1", failure_threshold=1, cooldown_seconds=0.001)
        breaker.record_failure()  # opens
        assert breaker.state == CircuitState.OPEN
        time.sleep(0.005)  # let cooldown elapse
        assert breaker.state == CircuitState.HALF_OPEN  # type: ignore[comparison-overlap]
        breaker.call()  # probe allowed in HALF_OPEN
        breaker.record_failure()  # probe fails -> reopen
        assert breaker.state == CircuitState.OPEN

    def test_half_open_probe_success_closes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        breaker = CircuitBreaker(name="p1", failure_threshold=1, cooldown_seconds=0.001)
        breaker.record_failure()
        time.sleep(0.005)
        assert breaker.state == CircuitState.HALF_OPEN
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED  # type: ignore[comparison-overlap]

    def test_reset(self) -> None:
        breaker = CircuitBreaker(name="p1", failure_threshold=1)
        breaker.record_failure()
        breaker.reset()
        assert breaker.state == CircuitState.CLOSED
        assert breaker._failure_count == 0
        assert breaker._opened_at is None


class TestTokenBudget:
    def test_allows_under_limit(self) -> None:
        budget = TokenBudget(name="p1", requests_per_min=3)
        assert budget.try_acquire() is True
        assert budget.try_acquire() is True
        assert budget.remaining_requests() == 1

    def test_blocks_when_exhausted(self) -> None:
        budget = TokenBudget(name="p1", requests_per_min=2)
        assert budget.try_acquire() is True
        assert budget.try_acquire() is True
        assert budget.try_acquire() is False

    def test_token_cap(self) -> None:
        budget = TokenBudget(name="p1", requests_per_min=100, tokens_per_min=100)
        assert budget.try_acquire(tokens=60) is True
        assert budget.try_acquire(tokens=60) is False  # 60+60 > 100

    def test_unlimited_tokens_by_default(self) -> None:
        budget = TokenBudget(name="p1", requests_per_min=100, tokens_per_min=0)
        assert budget.try_acquire(tokens=10_000) is True

    def test_reset(self) -> None:
        budget = TokenBudget(name="p1", requests_per_min=1)
        budget.try_acquire()
        budget.reset()
        assert budget.remaining_requests() == 1
