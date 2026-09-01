"""Memory coordinator — behavior lifecycle + store/retrieve orchestration.

Pattern-inherited from JARVIS ``app/memory/manager.py``. This is the ONLY class
external code should interact with inside the enriched memory path: it owns the
append/replace/ignore/delete behavior rules, coordinates the store, retriever,
and ranker, and exposes lifecycle callbacks. It is separate from - and can wrap
- the existing pluggable :class:`~app.memory.backends.MemoryBackend` seam.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.memory.hybrid import CandidateRetriever, KeywordRetriever
from app.memory.ranking import MemoryRanker, RankingWeights
from app.memory.schema import (
    BEHAVIOR_APPEND,
    BEHAVIOR_DELETE,
    BEHAVIOR_IGNORE,
    BEHAVIOR_REPLACE,
    IMPORTANCE_MEDIUM,
    SOURCE_USER,
    Memory,
    MemoryResult,
)
from app.memory.store import MemoryStore


class MemoryManager:
    """High-level memory orchestration.

    Handles behavior rules (append/replace/ignore/delete), coordinates the
    store + candidate retriever + ranker, and fires lifecycle callbacks.
    """

    def __init__(
        self,
        store: MemoryStore | None = None,
        path: str | None = None,
        retriever: CandidateRetriever | None = None,
        ranker: MemoryRanker | None = None,
        ranking_weights: RankingWeights | None = None,
    ) -> None:
        self._store = store or MemoryStore(path=path)
        self._retriever = retriever or KeywordRetriever()
        self._retriever.on_index_rebuilt(self._store.get_all())
        self._ranker = ranker or MemoryRanker(weights=ranking_weights)

        self._on_store: Callable[[Memory], None] | None = None
        self._on_update: Callable[[Memory], None] | None = None
        self._on_delete: Callable[[Memory], None] | None = None

    # ── High-level interface ─────────────────────────────────────────────
    def store(self, fact: dict[str, Any], source: str = SOURCE_USER) -> Memory | None:
        """Store a memory, applying behavior rules.

        ``fact`` requires ``category``, ``type``, ``value``; ``behavior`` and
        ``confidence``/``importance``/``metadata`` are optional.
        """
        behavior = fact.get("behavior", BEHAVIOR_APPEND)
        if behavior == BEHAVIOR_IGNORE:
            return None
        if behavior == BEHAVIOR_DELETE:
            self.delete_by_type(fact["category"], fact.get("type", ""))
            return None
        if behavior == BEHAVIOR_REPLACE:
            return self._handle_replace(fact, source)
        return self._handle_append(fact, source)

    def retrieve(self, prompt: str, limit: int | None = None) -> list[MemoryResult]:
        """Retrieve relevant memories: candidate discovery -> rank -> touch."""
        limit = limit or 20
        candidate_limit = min(limit * 3, max(self._store.count(), 1))
        candidates = self._retriever.find_candidates(prompt, limit=candidate_limit)
        results = self._ranker.rank(
            candidates=candidates,
            query=prompt,
            limit=limit,
            min_score=0.0,
        )
        if results:
            for result in results:
                result.memory.touch()
            self._store.force_save()
        return results

    def update(self, memory_id: str, updates: dict[str, Any]) -> Memory | None:
        memory = self._store.update_fields(memory_id, updates)
        if memory and self._on_update:
            self._on_update(memory)
        self._store.save_if_dirty()
        return memory

    def replace(self, fact: dict[str, Any], source: str = SOURCE_USER) -> Memory:
        """Replace a memory matching category+type, or append if none matches."""
        return self._handle_replace(fact, source)

    def delete(self, memory_id: str) -> bool:
        removed = self._store.remove(memory_id)
        if removed:
            self._retriever.on_memory_removed(memory_id)
            if self._on_delete:
                self._on_delete(removed)
            self._store.save()
            return True
        return False

    def delete_by_type(self, category: str, memory_type: str) -> int:
        removed = self._store.remove_by_category_and_type(category, memory_type)
        for memory in removed:
            self._retriever.on_memory_removed(memory.id)
            if self._on_delete:
                self._on_delete(memory)
        if removed:
            self._store.save()
        return len(removed)

    def merge(self, memory_id: str, new_data: dict[str, Any]) -> Memory | None:
        """Merge new data into an existing memory (append-if-new value)."""
        memory = self._store.get_by_id(memory_id)
        if memory is None:
            return self.update(memory_id, new_data)
        merged = dict(new_data)
        if "value" in merged and merged["value"] not in memory.value:
            merged["value"] = f"{memory.value}; {merged['value']}"
        return self.update(memory_id, merged)

    # ── Query pass-through ───────────────────────────────────────────────
    def get_all(self) -> list[Memory]:
        return self._store.get_all()

    def get_by_id(self, memory_id: str) -> Memory | None:
        return self._store.get_by_id(memory_id)

    def get_by_type(self, category: str, memory_type: str) -> list[Memory]:
        return self._store.find_by_category_and_type(category, memory_type)

    def count(self) -> int:
        return self._store.count()

    def clear(self) -> None:
        self._store.clear()
        self._retriever.clear()

    @property
    def is_dirty(self) -> bool:
        return self._store.is_dirty

    # ── Persistence ──────────────────────────────────────────────────────
    def save(self) -> None:
        self._store.save()

    def save_if_dirty(self) -> None:
        self._store.save_if_dirty()

    # ── Lifecycle callbacks ──────────────────────────────────────────────
    def on_store(self, callback: Callable[[Memory], None]) -> None:
        self._on_store = callback

    def on_update(self, callback: Callable[[Memory], None]) -> None:
        self._on_update = callback

    def on_delete(self, callback: Callable[[Memory], None]) -> None:
        self._on_delete = callback

    # ── Internal behaviour helpers ───────────────────────────────────────
    def _handle_append(self, fact: dict[str, Any], source: str) -> Memory:
        memory = Memory(
            category=fact["category"],
            memory_type=fact["type"],
            value=fact["value"],
            behavior=fact.get("behavior", BEHAVIOR_APPEND),
            source=source,
            confidence=float(fact.get("confidence", 1.0)),
            importance=float(fact.get("importance", IMPORTANCE_MEDIUM)),
            metadata=dict(fact["metadata"]) if fact.get("metadata") else {},
        )
        self._store.add(memory)
        self._retriever.on_memory_added(memory)
        if self._on_store:
            self._on_store(memory)
        self._store.save()
        return memory

    def _handle_replace(self, fact: dict[str, Any], source: str) -> Memory:
        existing = self._store.find_by_category_and_type(fact["category"], fact["type"])
        if existing:
            memory = existing[0]
            memory.value = fact["value"]
            memory.source = source
            if "confidence" in fact:
                memory.confidence = float(fact["confidence"])
            if "importance" in fact:
                memory.importance = float(fact["importance"])
            if fact.get("metadata"):
                memory.metadata = dict(fact["metadata"])
            memory.mark_updated()
            if self._on_update:
                self._on_update(memory)
            self._store.force_save()
            return memory
        return self._handle_append(fact, source)


__all__ = ["MemoryManager"]
