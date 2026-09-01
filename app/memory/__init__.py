"""Memory subsystem — hybrid memory with a JARVIS-parity management layer.

The memory layer now follows the same modular decomposition as JARVIS (and the
leading agent-memory frameworks): *storage* (durable :class:`MemoryStore` /
pluggable :class:`MemoryBackend`) -> *management* (:class:`MemoryManager` behavior
lifecycle) -> *retrieval* (keyword + dense hybrid candidates) -> *ranking*
(relevance x importance x frequency x recency x confidence). :class:`MemoryService`
provides the learner-namespaced façade the cognitive agents use.

The original thin backend seam remains intact (InMemory/Json/Chroma) for swap-in
compatibility; the enriched path rides on top of it via :class:`MemoryManager`.
"""

from app.memory.backends import (
    ChromaMemoryBackend,
    InMemoryBackend,
    JsonMemoryBackend,
    MemoryBackend,
    MemoryBackendError,
)
from app.memory.fact_extractor import extract_facts
from app.memory.hybrid import (
    CandidateRetriever,
    HybridRetriever,
    KeywordRetriever,
    VectorRetrieverAdapter,
)
from app.memory.manager import MemoryManager
from app.memory.ranking import DEFAULT_WEIGHTS, MemoryRanker, RankingWeights
from app.memory.reflexion import Reflection, ReflexionEngine
from app.memory.schema import (
    BEHAVIOR_APPEND,
    BEHAVIOR_DELETE,
    BEHAVIOR_IGNORE,
    BEHAVIOR_REPLACE,
    IMPORTANCE_CRITICAL,
    IMPORTANCE_HIGH,
    IMPORTANCE_LOW,
    IMPORTANCE_MEDIUM,
    SOURCE_INFERRED,
    SOURCE_SYSTEM,
    SOURCE_USER,
    Memory,
    MemoryResult,
)
from app.memory.service import MemoryService, MemoryStoreError
from app.memory.store import MemoryStore

__all__ = [
    "Memory",
    "MemoryResult",
    "MemoryBackend",
    "InMemoryBackend",
    "JsonMemoryBackend",
    "ChromaMemoryBackend",
    "MemoryBackendError",
    "MemoryStore",
    "MemoryManager",
    "MemoryRanker",
    "RankingWeights",
    "DEFAULT_WEIGHTS",
    "CandidateRetriever",
    "KeywordRetriever",
    "HybridRetriever",
    "VectorRetrieverAdapter",
    "extract_facts",
    "MemoryService",
    "MemoryStoreError",
    "ReflexionEngine",
    "Reflection",
    "IMPORTANCE_LOW",
    "IMPORTANCE_MEDIUM",
    "IMPORTANCE_HIGH",
    "IMPORTANCE_CRITICAL",
    "BEHAVIOR_APPEND",
    "BEHAVIOR_REPLACE",
    "BEHAVIOR_IGNORE",
    "BEHAVIOR_DELETE",
    "SOURCE_USER",
    "SOURCE_SYSTEM",
    "SOURCE_INFERRED",
]
