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

    def __contains__(self, document_id: str) -> bool:
        """Check if a document exists."""
        return self.get(document_id) is not None


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


class ChromaMemoryBackend(MemoryBackend):
    """ChromaDB-backed memory backend with dense vector retrieval.

    Uses ChromaDB's built-in embedding function (default: all-MiniLM-L6-v2)
    for semantic search. Implements the same interface as InMemoryBackend
    and JsonMemoryBackend so callers can swap backends without changes.
    """

    def __init__(
        self,
        persist_directory: str | Path,
        collection_name: str = "professor_memory",
        embedding_function: Any = None,
    ) -> None:
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name

        import chromadb
        from chromadb.config import Settings

        self._client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(anonymized_telemetry=False),
        )

        # Use default embedding function if none provided
        if embedding_function is None:
            from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

            embedding_function = DefaultEmbeddingFunction()

        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=embedding_function,
        )

    def add(self, document_id: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        # ChromaDB requires non-empty metadata dict
        meta = metadata or {}
        if not meta:
            meta = {"_placeholder": True}
        self._collection.add(
            ids=[document_id],
            documents=[text],
            metadatas=[meta],
        )

    def get(self, document_id: str) -> MemoryItem | None:
        result = self._collection.get(ids=[document_id])
        ids = result.get("ids")
        if not ids:
            return None
        documents = result.get("documents")
        metadatas = result.get("metadatas")
        return MemoryItem(
            document_id=ids[0],
            text=documents[0] if documents else "",
            metadata=dict(metadatas[0]) if metadatas else {},
        )

    def search(self, query: str, k: int = 5) -> list[MemoryItem]:
        result = self._collection.query(
            query_texts=[query],
            n_results=k,
        )
        items: list[MemoryItem] = []
        ids = result.get("ids")
        documents = result.get("documents")
        metadatas = result.get("metadatas")
        if ids and ids[0] and documents and documents[0] and metadatas and metadatas[0]:
            for doc_id, doc_text, metadata in zip(ids[0], documents[0], metadatas[0], strict=False):
                items.append(MemoryItem(doc_id, doc_text, dict(metadata) if metadata else {}))
        return items

    def delete(self, document_id: str) -> None:
        self._collection.delete(ids=[document_id])

    def count(self) -> int:
        return self._collection.count()

    def keys(self) -> list[str]:
        result = self._collection.get()
        return result["ids"] if result["ids"] else []


__all__ = [
    "MemoryBackend",
    "InMemoryBackend",
    "JsonMemoryBackend",
    "ChromaMemoryBackend",
    "MemoryItem",
    "MemoryBackendError",
]
