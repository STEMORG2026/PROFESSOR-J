"""Candidate memory retrieval — keyword + dense-vector hybrid.

Pattern-inherited from JARVIS ``app/memory/retrieval.py`` +
``app/memory/hybrid_retriever.py`` + ``app/memory/vector_retriever.py``.

Retrieval only *discovers* candidate memories (it does not rank them —
:class:`~app.memory.ranking.MemoryRanker` scores and sorts). The hybrid runs
keyword and vector candidate discovery in parallel and deduplicates by ID.
"""

from __future__ import annotations

from typing import Any, Protocol

from app.memory.backends import MemoryBackend, MemoryItem
from app.memory.schema import Memory
from app.utils.text import STOP_WORDS, extract_keywords


class CandidateRetriever(Protocol):
    """Protocol for candidate retrieval engines."""

    def find_candidates(self, query: str, limit: int = 50) -> list[Memory]: ...

    def on_memory_added(self, memory: Memory) -> None: ...

    def on_memory_removed(self, memory_id: str) -> None: ...

    def on_index_rebuilt(self, memories: list[Memory]) -> None: ...

    def clear(self) -> None: ...


class KeywordRetriever:
    """Keyword-overlap candidate retrieval (sparse)."""

    def __init__(self, min_keyword_overlap: int = 1) -> None:
        self._memories: list[Memory] = []
        self._min_overlap = min_keyword_overlap

    def find_candidates(self, query: str, limit: int = 50) -> list[Memory]:
        if not self._memories or not query:
            return []
        query_keywords = extract_keywords(query, STOP_WORDS)
        if not query_keywords:
            return []
        scored: list[tuple[int, Memory]] = []
        for memory in self._memories:
            memory_keywords = self._get_memory_keywords(memory)
            overlap = len(query_keywords & memory_keywords)
            if overlap >= self._min_overlap:
                scored.append((overlap, memory))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [memory for _, memory in scored[:limit]]

    def on_memory_added(self, memory: Memory) -> None:
        if memory not in self._memories:
            self._memories.append(memory)

    def on_memory_removed(self, memory_id: str) -> None:
        self._memories = [m for m in self._memories if m.id != memory_id]

    def on_index_rebuilt(self, memories: list[Memory]) -> None:
        self._memories = list(memories)

    def clear(self) -> None:
        self._memories.clear()

    @staticmethod
    def _get_memory_keywords(memory: Memory) -> set[str]:
        return extract_keywords(
            f"{memory.value} {memory.category} {memory.memory_type}", STOP_WORDS
        )


class HybridRetriever:
    """Combines keyword and vector retrieval, deduplicating by ID.

    Satisfies the :class:`CandidateRetriever` Protocol — drop-in for either
    retriever alone. Why both: keyword catches exact matches, vector catches
    semantic matches; neither alone is sufficient.
    """

    def __init__(
        self, keyword: CandidateRetriever, vector: CandidateRetriever | None = None
    ) -> None:
        self._keyword = keyword
        self._vector = vector

    def find_candidates(self, query: str, limit: int = 50) -> list[Memory]:
        kw = self._keyword.find_candidates(query, limit)
        vec = self._vector.find_candidates(query, limit) if self._vector else []
        seen: set[str] = set()
        combined: list[Memory] = []
        for memory in [*kw, *vec]:
            if memory.id not in seen:
                seen.add(memory.id)
                combined.append(memory)
        return combined[:limit]

    def on_memory_added(self, memory: Memory) -> None:
        self._keyword.on_memory_added(memory)
        if self._vector:
            self._vector.on_memory_added(memory)

    def on_memory_removed(self, memory_id: str) -> None:
        self._keyword.on_memory_removed(memory_id)
        if self._vector:
            self._vector.on_memory_removed(memory_id)

    def on_index_rebuilt(self, memories: list[Memory]) -> None:
        self._keyword.on_index_rebuilt(memories)
        if self._vector:
            self._vector.on_index_rebuilt(memories)

    def clear(self) -> None:
        self._keyword.clear()
        if self._vector:
            self._vector.clear()


# Screened adapter so callers can reuse the existing ChromaMemoryBackend as
# the dense candidate engine without a second code path.
class VectorRetrieverAdapter:
    """Wraps a dense :class:`MemoryBackend` as a :class:`CandidateRetriever`.

    Lets the ChromaMemoryBackend (dense embeddings) feed the hybrid retriever
    while reusing its existing implementation and persistence.
    """

    def __init__(self, backend: MemoryBackend) -> None:
        self._backend = backend

    def find_candidates(self, query: str, limit: int = 50) -> list[Memory]:
        items = self._backend.search(query, k=limit)
        out: list[Memory] = []
        for item in items:
            out.append(self._memoryitem_to_memory(item))
        return out

    def on_memory_added(self, memory: Memory) -> None:
        self._backend.add(memory.id, _memory_to_text(memory), _memory_to_metadata(memory))

    def on_memory_removed(self, memory_id: str) -> None:
        self._backend.delete(memory_id)

    def on_index_rebuilt(self, memories: list[Memory]) -> None:
        self._backend.clear()
        for memory in memories:
            self._backend.add(memory.id, _memory_to_text(memory), _memory_to_metadata(memory))

    def clear(self) -> None:
        self._backend.clear()

    @staticmethod
    def _memoryitem_to_memory(item: MemoryItem) -> Memory:
        return Memory.from_dict(
            {
                "id": item.document_id,
                "category": (item.metadata or {}).get("category", "general"),
                "type": (item.metadata or {}).get("memory_type", "fact"),
                "value": item.text,
                "metadata": item.metadata or {},
            }
        )


def _memory_to_text(memory: Memory) -> str:
    return f"{memory.category} {memory.memory_type}: {memory.value}"


def _memory_to_metadata(memory: Memory) -> dict[str, Any]:
    return {
        "category": memory.category,
        "memory_type": memory.memory_type,
        "behavior": memory.behavior,
        "source": memory.source,
        "confidence": memory.confidence,
        "importance": memory.importance,
        "access_count": memory.access_count,
    }


__all__ = [
    "CandidateRetriever",
    "KeywordRetriever",
    "HybridRetriever",
    "VectorRetrieverAdapter",
]
