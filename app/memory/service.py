"""MemoryService — learner-namespaced, cross-session memory for the brain.

Wraps a :class:`~app.memory.backends.MemoryBackend` and scopes documents by
learner id, giving each learner durable, searchable notes that persist across
sessions (the memory seam Phase 4 exposes to the cognitive agents). Callers only
ever talk to this service, never to a backend directly.
"""

from __future__ import annotations

from typing import Any

from app.exceptions import ProfessorError
from app.memory.backends import MemoryBackend


class MemoryStoreError(ProfessorError):
    """Raised for memory-service-level failures."""

    code = "MEMORY_STORE"


class MemoryService:
    """Namespaced store/recall over a :class:`MemoryBackend`."""

    def __init__(self, backend: MemoryBackend) -> None:
        self.backend = backend

    def _key(self, namespace: str, document_id: str) -> str:
        return f"{namespace}::{document_id}"

    def remember(
        self,
        learner_id: str,
        text: str,
        document_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Store a memory item for a learner; returns its effective document id."""
        if not text or not text.strip():
            raise MemoryStoreError("Cannot remember empty text")
        import uuid

        doc_id = document_id or f"mem-{uuid.uuid4().hex[:8]}"
        self.backend.add(
            self._key(learner_id, doc_id), text, {"learner_id": learner_id, **(metadata or {})}
        )
        return doc_id

    def recall(self, learner_id: str, query: str, k: int = 5) -> list[dict[str, Any]]:
        """Retrieve the top-k learner memories relevant to ``query``."""
        items = self.backend.search(query, k=k)
        results = []
        for item in items:
            if item.metadata.get("learner_id") != learner_id:
                continue
            results.append(
                {
                    "document_id": item.document_id.split("::", 1)[-1],
                    "text": item.text,
                    "metadata": item.metadata,
                }
            )
        return results[:k]

    def forget(self, learner_id: str, document_id: str) -> bool:
        """Delete one learner memory; returns whether it existed."""
        key = self._key(learner_id, document_id)
        existed = self.backend.get(key) is not None
        self.backend.delete(key)
        return existed

    def count(self, learner_id: str) -> int:
        """Number of memory items stored for a learner."""
        prefix = f"{learner_id}::"
        known = self.backend.keys()
        return sum(1 for k in known if k.startswith(prefix))


__all__ = ["MemoryService", "MemoryStoreError"]
