"""Model router — multi-provider failover with circuit breakers and budgets.

Routes generation requests across the catalog, honoring per-provider token
budgets and 3-state circuit breakers. Falls over on retryable failures
(rate-limit, timeout, circuit-open) and raises :class:`NoHealthyProvidersError`
when every provider is unavailable.
"""

from __future__ import annotations

import logging
from typing import Any

from app.exceptions import (
    CircuitOpenError,
    NoHealthyProvidersError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.models.catalog import ProviderCatalog
from app.models.providers import LLMMessage, LLMProvider, LLMResult
from app.resources.budget import TokenBudget
from app.resources.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

_RETRYABLE_CODES = {"PROVIDER_RATE_LIMIT", "PROVIDER_TIMEOUT"}


class ModelRouter:
    """Routes to the first healthy provider; fails over on retryable errors."""

    def __init__(self, catalog: ProviderCatalog | None = None) -> None:
        self.catalog = catalog or ProviderCatalog()
        self._breakers: dict[str, CircuitBreaker] = {}
        self._budgets: dict[str, TokenBudget] = {}

    @property
    def provider_names(self) -> list[str]:
        return self.catalog.names()

    def _breaker(self, name: str) -> CircuitBreaker:
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name=name)
        return self._breakers[name]

    def _budget(self, name: str) -> TokenBudget:
        if name not in self._budgets:
            self._budgets[name] = TokenBudget(name=name)
        return self._budgets[name]

    def register_provider(self, provider: LLMProvider) -> None:
        self.catalog.register(provider)

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        preferred: str | None = None,
        **kwargs: Any,
    ) -> LLMResult:
        """Generate a completion, failing over across healthy providers.

        ``preferred`` names a provider to try first (e.g. a user-selected one);
        it is skipped if unhealthy.
        """
        ordered = self._ordered_names(preferred)
        last_error: Exception | None = None
        tried: list[str] = []

        for name in ordered:
            provider = self.catalog.get(name)
            if provider is None:
                continue
            breaker = self._breaker(name)
            budget = self._budget(name)
            try:
                breaker.call()
            except CircuitOpenError as e:
                logger.info("Skipping %s: circuit open", name)
                last_error = e
                tried.append(name)
                continue
            if not budget.try_acquire():
                logger.info("Skipping %s: budget exhausted", name)
                last_error = ProviderRateLimitError(provider=name, retry_after=1)
                tried.append(name)
                continue
            try:
                result = await self._call(provider, messages, **kwargs)
                breaker.record_success()
                return result
            except (
                ProviderRateLimitError,
                ProviderTimeoutError,
                ProviderUnavailableError,
            ) as e:
                breaker.record_failure()
                logger.warning("Provider %s failed (%s); failing over", name, e.code)
                last_error = e
                tried.append(name)
            except ProviderAuthError as e:
                # Not retryable; skip without tripping the breaker.
                logger.error("Provider %s auth failed; skipping", name)
                last_error = e
                tried.append(name)
            finally:
                budget.release()

        raise NoHealthyProvidersError(providers=tried, cause=last_error)

    async def _call(
        self, provider: LLMProvider, messages: list[LLMMessage], **kwargs: Any
    ) -> LLMResult:
        try:
            return await provider.complete(messages, **kwargs)
        except ProviderRateLimitError:
            raise
        except ProviderTimeoutError:
            raise
        except CircuitOpenError:
            raise
        except Exception as e:
            # Map transport/HTTP failures onto a typed, retryable error.
            raise ProviderUnavailableError(provider=provider.name, message=str(e)) from e

    def _ordered_names(self, preferred: str | None) -> list[str]:
        names = self.catalog.names()
        if preferred and preferred in names:
            return [preferred, *(n for n in names if n != preferred)]
        return names
