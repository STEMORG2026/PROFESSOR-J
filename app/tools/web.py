"""Web Tools — search and fetch capabilities.

Modeled on Hermes `web_tools.py`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A web search result."""

    url: str
    title: str
    snippet: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FetchResult:
    """Result of fetching a URL."""

    url: str
    status_code: int
    content: str
    content_type: str
    metadata: dict[str, Any] = field(default_factory=dict)


class WebSearch:
    """Web search capabilities."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    async def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        """Search the web."""
        # Placeholder — in production, use Brave API, Serper, etc.
        logger.info("Searching: %s", query)
        return []

    async def fetch(self, url: str) -> FetchResult:
        """Fetch a URL."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url)
            return FetchResult(
                url=url,
                status_code=resp.status_code,
                content=resp.text,
                content_type=resp.headers.get("content-type", ""),
            )
        except Exception as exc:
            return FetchResult(
                url=url,
                status_code=0,
                content=str(exc),
                content_type="error",
            )


def create_web_search(api_key: str | None = None) -> WebSearch:
    """Create web search."""
    return WebSearch(api_key)


__all__ = ["WebSearch", "SearchResult", "FetchResult", "create_web_search"]
