"""Per-provider token/request budget tracking for rate-limit resilience."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field


@dataclass(slots=True)
class TokenBudget:
    """A rolling-window rpms/tpms budget.

    ``requests_per_min`` and ``tokens_per_min`` bound how many requests and how
    many tokens may be issued in a rolling minute. Callers use
    :meth:`try_acquire` before dispatching and :meth:`release` after.
    """

    name: str
    requests_per_min: int = 60
    tokens_per_min: int = 0  # 0 = unlimited tokens
    _window_seconds: float = 60.0
    _events: deque[tuple[float, int]] = field(default_factory=deque)

    def try_acquire(self, tokens: int = 0) -> bool:
        """Return True if the request fits within the budget; account for it."""
        now = time.monotonic()
        self._prune(now)
        request_count = len(self._events)
        token_count = sum(t for _, t in self._events)
        if request_count >= self.requests_per_min:
            return False
        if self.tokens_per_min and token_count + tokens > self.tokens_per_min:
            return False
        self._events.append((now, tokens))
        return True

    def release(self, tokens: int = 0) -> None:
        """Return accounting for a request that was counted but not sent."""
        self._prune(time.monotonic())
        pass  # tokens are accounted at acquisition; release is a no-op for the window model

    def remaining_requests(self) -> int:
        now = time.monotonic()
        self._prune(now)
        return max(0, self.requests_per_min - len(self._events))

    def reset(self) -> None:
        self._events.clear()

    def _prune(self, now: float) -> None:
        cutoff = now - self._window_seconds
        while self._events and self._events[0][0] < cutoff:
            self._events.popleft()
