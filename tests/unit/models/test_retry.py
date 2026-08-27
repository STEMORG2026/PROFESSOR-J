"""Tests for bounded jittered retry honoring retry_after."""

from __future__ import annotations

import pytest

from app.exceptions import ProviderRateLimitError, ProviderTimeoutError
from app.models.retry import _delay, bounded_retry


class TestBoundedRetry:
    @pytest.mark.asyncio
    async def test_succeeds_on_first_attempt(self) -> None:
        calls = 0

        async def op() -> str:
            nonlocal calls
            calls += 1
            return "ok"

        assert await bounded_retry(op, sleep=_noop_sleep) == "ok"
        assert calls == 1

    @pytest.mark.asyncio
    async def test_retries_then_succeeds(self) -> None:
        calls = 0

        async def op() -> str:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise ProviderRateLimitError(provider="x", retry_after=1)
            return "ok"

        result = await bounded_retry(op, max_attempts=3, sleep=_noop_sleep)
        assert result == "ok"
        assert calls == 3

    @pytest.mark.asyncio
    async def test_gives_up_after_max_attempts(self) -> None:
        calls = 0

        async def op() -> str:
            nonlocal calls
            calls += 1
            raise ProviderTimeoutError(provider="x", timeout=1.0)

        with pytest.raises(ProviderTimeoutError):
            await bounded_retry(op, max_attempts=2, sleep=_noop_sleep)
        assert calls == 2

    @pytest.mark.asyncio
    async def test_max_attempts_one_disables_retry(self) -> None:
        calls = 0

        async def op() -> str:
            nonlocal calls
            calls += 1
            raise ProviderRateLimitError(provider="x", retry_after=1)

        with pytest.raises(ProviderRateLimitError):
            await bounded_retry(op, max_attempts=1, sleep=_noop_sleep)
        assert calls == 1

    @pytest.mark.asyncio
    async def test_honors_retry_after_in_sleep(self) -> None:
        sleeps: list[float] = []

        async def fake_sleep(delay: float) -> None:
            sleeps.append(delay)

        calls = 0

        async def op() -> str:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ProviderRateLimitError(provider="x", retry_after=1)
            return "ok"

        await bounded_retry(op, max_attempts=3, base_delay=0.01, jitter=False, sleep=fake_sleep)
        # First retry must sleep at least retry_after=1 (bounded by max_delay=2).
        assert sleeps[0] == 1.0
        assert calls == 2

    def test_delay_exponential_and_capped(self) -> None:
        # attempt 1: base; attempt 3: base*4 capped at max_delay.
        d1 = _delay(0.5, 2.0, 1, None, jitter=False)
        d3 = _delay(0.5, 2.0, 3, None, jitter=False)
        assert d1 == 0.5
        assert d3 == 2.0  # 0.5 * 2**2 = 2.0, which equals the max_delay cap
        capped = _delay(0.5, 2.0, 4, None, jitter=False)  # 0.5*2**3 = 4.0 -> capped
        assert capped == 2.0


async def _noop_sleep(delay: float) -> None:
    del delay
