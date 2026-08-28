"""Memory subsystem — pluggable hybrid memory backend + MemoryService.

The memory layer is behind an abstract :class:`MemoryBackend` so the Phase 4
in-memory/JSON implementations can later be swapped for ChromaDB (dense) + BM25
(sparse) without touching callers. :class:`MemoryService` namespaces documents by
learner, giving the brain a persistent cross-session memory.
"""

from app.memory.backends import (
    InMemoryBackend,
    JsonMemoryBackend,
    MemoryBackend,
    MemoryBackendError,
)
from app.memory.service import MemoryService, MemoryStoreError

__all__ = [
    "MemoryBackend",
    "InMemoryBackend",
    "JsonMemoryBackend",
    "MemoryBackendError",
    "MemoryService",
    "MemoryStoreError",
]
