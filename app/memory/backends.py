"""Memory backend abstraction + in-memory and JSON-file implementations.

:class:`MemoryBackend` is the Phase 4 seam: callers depend only on this
interface, so a dense ChromaDB + sparse BM25 backend can be dropped in later
without changing the brain. The concrete backends here are deterministic and
dependency-free (suited to tests and local development).
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

from app.domain.time import utc_now
from app.exceptions import ProfessorError

logger = logging.getLogger(__name__)


class MemoryBackendError(ProfessorError):
    """Base memory-backend failure."""

    code = "MEMORY_BACKEND"


class MemoryItem:
    """A stored memory document."""

    __slots__ = ("document_id", "text", "metadata", "created_at")

    def __init__(
        self,
        document_id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> None:
        self.document_id = document_id
        self.text = text
        self.metadata = metadata or {}
        self.created_at = created_at or utc_now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "text": self.text,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryItem:
        return cls(
            document_id=data["document_id"],
            text=data["text"],
            metadata=dict(data.get("metadata", {})),
        )


class MemoryBackend(ABC):
    """Pluggable document memory."""

    @abstractmethod
    def add(self, document_id: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        """Store a document."""

    @abstractmethod
    def get(self, document_id: str) -> MemoryItem | None:
        """Retrieve a document by id."""

    @abstractmethod
    def search(self, query: str, k: int = 5) -> list[MemoryItem]:
        """Return the top-k most relevant documents for ``query``."""

    @abstractmethod
    def delete(self, document_id: str) -> None:
        """Delete a document."""

    @abstractmethod
    def count(self) -> int:
        """Number of stored documents."""

    @abstractmethod
    def keys(self) -> list[str]:
        """List stored document ids (for namespace lookups)."""


def _tokenize(text: str) -> set[str]:
    return {tok for tok in text.lower().split() if len(tok) > 1}


class InMemoryBackend(MemoryBackend):
    """Volatile in-memory backend with a simple overlap scorer."""

    def __init__(self) -> None:
        self._items: dict[str, MemoryItem] = {}

    def add(self, document_id: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        self._items[document_id] = MemoryItem(document_id, text, metadata)

    def get(self, document_id: str) -> MemoryItem | None:
        return self._items.get(document_id)

    def search(self, query: str, k: int = 5) -> list[MemoryItem]:
        q_tokens = _tokenize(query)
        scored: list[tuple[float, MemoryItem]] = []
        for item in self._items.values():
            doc_tokens = _tokenize(item.text)
            if not doc_tokens:
                continue
            overlap = len(q_tokens & doc_tokens)
            if overlap:
                scored.append((overlap / len(doc_tokens), item))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [item for _, item in scored[:k]]

    def delete(self, document_id: str) -> None:
        self._items.pop(document_id, None)

    def count(self) -> int:
        return len(self._items)

    def keys(self) -> list[str]:
        return list(self._items.keys())


class JsonMemoryBackend(MemoryBackend):
    """JSON-file-backed backend for durable local memory.

    All documents are written to a single JSON array file, rewritten on each
    change. Suitable for local/dev; swap for ChromaDB in production.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._items: dict[str, MemoryItem] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            for raw in data:
                item = MemoryItem.from_dict(raw)
                self._items[item.document_id] = item
        except (json.JSONDecodeError, KeyError, TypeError):
            logger.warning("Corrupt memory file, starting empty: %s", self.path)
            self._items = {}

    def _flush(self) -> None:
        payload = [item.to_dict() for item in self._items.values()]
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def add(self, document_id: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        self._items[document_id] = MemoryItem(document_id, text, metadata)
        self._flush()

    def get(self, document_id: str) -> MemoryItem | None:
        return self._items.get(document_id)

    def search(self, query: str, k: int = 5) -> list[MemoryItem]:
        q_tokens = _tokenize(query)
        scored: list[tuple[float, MemoryItem]] = []
        for item in self._items.values():
            doc_tokens = _tokenize(item.text)
            if not doc_tokens:
                continue
            overlap = len(q_tokens & doc_tokens)
            if overlap:
                scored.append((overlap / len(doc_tokens), item))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [item for _, item in scored[:k]]

    def delete(self, document_id: str) -> None:
        self._items.pop(document_id, None)
        self._flush()

    def count(self) -> int:
        return len(self._items)

    def keys(self) -> list[str]:
        return list(self._items.keys())


__all__ = [
    "MemoryBackend",
    "InMemoryBackend",
    "JsonMemoryBackend",
    "MemoryItem",
    "MemoryBackendError",
]
