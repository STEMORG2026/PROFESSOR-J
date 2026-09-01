"""MemoryService — learner-namespaced, cross-session memory for the brain.

Wraps the enriched :class:`~app.memory.manager.MemoryManager` (JARVIS parity:
behavior lifecycle, hybrid ranking) while preserving the original
learner-namespaced ``remember``/``recall``/``forget``/``count`` surface used by
the brain and :class:`~app.memory.reflexion.ReflexionEngine`.

Callers depend only on this service, never on a backend or manager directly.
"""

from __future__ import annotations

from typing import Any

from app.exceptions import ProfessorError
from app.memory.manager import MemoryManager
from app.memory.schema import Memory


class MemoryStoreError(ProfessorError):
    """Raised for memory-service-level failures."""

    code = "MEMORY_STORE"


# Namespace where cross-session learner memories live in the backend.
_NAMESPACE = "learner"


class MemoryService:
    """Namespaced store/recall over a :class:`MemoryManager`."""

    def __init__(self, manager: MemoryManager | None = None) -> None:
        self._manager = manager or MemoryManager()

    # ── Legacy learner-namespaced surface (backward compatible) ──────────
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
        self._manager.store(
            {
                "category": metadata.get("category", "learner") if metadata else "learner",
                "type": metadata.get("memory_type", "fact") if metadata else "fact",
                "value": text,
                "behavior": "append",
                "metadata": {"learner_id": learner_id, "namespace": _NAMESPACE, **(metadata or {})},
            }
        )
        return doc_id

    def recall(self, learner_id: str, query: str, k: int = 5) -> list[dict[str, Any]]:
        """Retrieve the top-k learner memories relevant to ``query``."""
        # Candidate retrieval + ranking across the whole store, then filter by
        # learner namespace and metadata.
        results = self._manager.retrieve(query, limit=k * 4)
        out: list[dict[str, Any]] = []
        for result in results:
            meta = result.memory.metadata or {}
            if meta.get("learner_id") != learner_id:
                continue
            out.append(
                {
                    "document_id": result.memory.id,
                    "text": result.memory.value,
                    "score": result.score,
                    "metadata": meta,
                }
            )
            if len(out) >= k:
                break
        return out

    def forget(self, learner_id: str, document_id: str) -> bool:
        """Delete one learner memory; returns whether it existed."""
        memory = self._manager.get_by_id(document_id)
        if memory is None:
            return False
        meta = memory.metadata or {}
        if meta.get("learner_id") != learner_id:
            return False
        return self._manager.delete(document_id)

    def count(self, learner_id: str) -> int:
        """Number of memory items stored for a learner."""
        return sum(
            1 for m in self._manager.get_all() if (m.metadata or {}).get("learner_id") == learner_id
        )

    # ── Enriched JARVIS-parity façade ────────────────────────────────────
    def store_memory(
        self,
        key: str,
        value: str,
        category: str = "general",
        behavior: str = "append",
        confidence: float = 1.0,
        importance: float = 0.5,
        source: str = "user",
        metadata: dict[str, Any] | None = None,
    ) -> Memory | None:
        """Store a memory record and return the stored memory."""
        return self._manager.store(
            {
                "category": category,
                "type": key,
                "value": value,
                "behavior": behavior,
                "confidence": confidence,
                "importance": importance,
                "source": source,
                "metadata": metadata or {},
            }
        )

    def search_memories(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Hybrid-rank and return the top memories for ``query``."""
        results = self._manager.retrieve(query, limit=limit)
        out: list[dict[str, Any]] = []
        for result in results:
            m: Memory = result.memory
            out.append(
                {
                    "id": m.id,
                    "key": m.memory_type,
                    "value": m.value,
                    "category": m.category,
                    "confidence": result.score,
                    "access_count": m.access_count,
                    "metadata": m.metadata or {},
                }
            )
        return out

    def extract_facts(self, conversation_text: str, source: str = "user") -> list[dict[str, Any]]:
        """Extract + store structured facts from conversation text (rule-based)."""
        from app.memory.fact_extractor import extract_facts

        facts = extract_facts(conversation_text, source=source)
        stored = []
        for fact in facts:
            memory = self._manager.store(fact, source=source)
            if memory is not None:
                stored.append(memory.to_dict())
        return stored

    def list_memories(self) -> list[dict[str, Any]]:
        """Return all stored memories as dicts."""
        return [m.to_dict() for m in self._manager.get_all()]

    def get_by_type(self, category: str, memory_type: str) -> list[dict[str, Any]]:
        return [m.to_dict() for m in self._manager.get_by_type(category, memory_type)]


__all__ = ["MemoryService", "MemoryStoreError"]
