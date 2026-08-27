"""Bounded retry with jittered backoff for retryable provider errors.

Honors ``retry_after`` from :class:`ProviderRateLimitError` and uses bounded
jittered exponential backoff, with a hard cap on attempts. This composes with
:class:`ModelRouter` failover: retry within a provider, then fail over.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

from app.exceptions import (
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

P = ParamSpec("P")
T = TypeVar("T")

_RETRYABLE = (ProviderRateLimitError, ProviderTimeoutError, ProviderUnavailableError)


async def bounded_retry(
    operation: Callable[..., Awaitable[T]],
    *,
    max_attempts: int = 3,
    base_delay: float = 0.05,
    max_delay: float = 2.0,
    jitter: bool = True,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> T:
    """Call ``operation`` with retries on retryable errors.

    ``max_attempts=1`` disables retry. ``retry_after`` from a rate-limit error
    overrides the backoff delay for that attempt (bounded by ``max_delay``).
    ``sleep`` is injectable for deterministic tests.
    """
    if max_attempts < 1:
        max_attempts = 1
    do_sleep = sleep or asyncio.sleep
    attempt = 0
    last_error: Exception | None = None
    while attempt < max_attempts:
        attempt += 1
        try:
            return await operation()
        except _RETRYABLE as e:
            last_error = e
            if attempt >= max_attempts:
                break
            retry_after = _retry_after(e)
            await do_sleep(_delay(base_delay, max_delay, attempt, retry_after, jitter))
    assert last_error is not None
    raise last_error


def _retry_after(error: BaseException) -> float | None:
    """Extract retry_after from a rate-limit error context if present."""
    ctx = getattr(error, "context", None)
    if isinstance(ctx, dict):
        ra = ctx.get("retry_after")
        if isinstance(ra, (int, float)) and ra > 0:
            return float(ra)
    return None


def _delay(
    base: float, max_delay: float, attempt: int, retry_after: float | None, jitter: bool
) -> float:
    backoff: float = min(max_delay, base * (2 ** (attempt - 1)))
    if retry_after is not None:
        delay_raw: float = min(max_delay, max(backoff, retry_after))
    else:
        delay_raw = backoff
    if jitter:
        delay_raw *= random.uniform(0.5, 1.5)  # noqa: S311 - bounded jitter, not security
    return min(max_delay, delay_raw)
