"""Resource management — circuit breakers and rate-limit budgets.

Provides the 3-state circuit-breaker used by the model router to fail over
between providers and bound the blast radius of a failing provider.
"""

from app.resources.budget import TokenBudget  # noqa: F401
from app.resources.circuit_breaker import CircuitBreaker, CircuitState  # noqa: F401

__all__ = ["CircuitBreaker", "CircuitState", "TokenBudget"]
