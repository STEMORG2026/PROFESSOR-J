"""Rich memory schema — the durable unit of learner memory (Phase 4, JARVIS parity).

Pattern-inherited from JARVIS ``app/memory/schema.py``: a single :class:`Memory`
carries category, type, behavior (append/replace/ignore/delete), immutable
``created_at`` + mutable ``updated_at``/``last_used``, source, confidence,
importance, and access-count (the signals the ranker feeds on).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

# Behavior policies
BEHAVIOR_APPEND = "append"
BEHAVIOR_REPLACE = "replace"
BEHAVIOR_IGNORE = "ignore"
BEHAVIOR_DELETE = "delete"

# Source provenance
SOURCE_USER = "user"
SOURCE_SYSTEM = "system"
SOURCE_INFERRED = "inferred"

# Importance levels
IMPORTANCE_LOW = 0.3
IMPORTANCE_MEDIUM = 0.5
IMPORTANCE_HIGH = 0.7
IMPORTANCE_CRITICAL = 0.9


@dataclass
class Memory:
    """A single durable memory with rich ranking metadata.

    Timestamps are epoch seconds (floats) for easy arithmetic in the ranker.
    ``created_at`` is immutable; ``updated_at`` and ``last_used`` are mutable.
    """

    category: str  # e.g. "identity", "preference", "skill", "learner"
    memory_type: str  # e.g. "name", "like", "fact"
    value: str  # the actual content
    behavior: str = BEHAVIOR_APPEND  # append | replace | ignore | delete

    id: str = field(default_factory=lambda: uuid4().hex[:8])

    created_at: float = field(default_factory=time.time)  # immutable
    updated_at: float = field(default_factory=time.time)  # mutable
    last_used: float = field(default_factory=time.time)  # mutable (recency)

    source: str = SOURCE_USER  # user | system | inferred
    confidence: float = 1.0  # 0.0–1.0
    importance: float = IMPORTANCE_MEDIUM  # 0.0–1.0
    access_count: int = 0

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "type": self.memory_type,
            "value": self.value,
            "behavior": self.behavior,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_used": self.last_used,
            "source": self.source,
            "confidence": self.confidence,
            "importance": self.importance,
            "access_count": self.access_count,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Memory:
        """Deserialize with tolerance for older/v1 shapes."""
        created = data.get("created_at", data.get("timestamp", time.time()))
        updated = data.get("updated_at", data.get("timestamp", time.time()))
        last_used = data.get("last_used", updated)
        return cls(
            id=str(data.get("id", uuid4().hex[:8])),
            category=str(data["category"]),
            memory_type=str(data["type"]),
            value=str(data["value"]),
            behavior=str(data.get("behavior", BEHAVIOR_APPEND)),
            created_at=float(created),
            updated_at=float(updated),
            last_used=float(last_used),
            source=str(data.get("source", SOURCE_USER)),
            confidence=float(data.get("confidence", 1.0)),
            importance=float(data.get("importance", IMPORTANCE_MEDIUM)),
            access_count=int(data.get("access_count", 0)),
            metadata=dict(data.get("metadata", {}) or {}),
        )

    def touch(self) -> None:
        """Mark as retrieved: bump last_used and access_count."""
        self.last_used = time.time()
        self.access_count += 1

    def mark_updated(self) -> None:
        """Mark as modified (called on updates)."""
        self.updated_at = time.time()

    def format_for_prompt(self) -> str:
        """Format this memory for inclusion in a prompt."""
        return f"- [{self.category}] {self.memory_type}: {self.value}"


@dataclass
class MemoryResult:
    """A retrieved memory with its relevance score."""

    memory: Memory
    score: float = 0.0


__all__ = [
    "Memory",
    "MemoryResult",
    "BEHAVIOR_APPEND",
    "BEHAVIOR_REPLACE",
    "BEHAVIOR_IGNORE",
    "BEHAVIOR_DELETE",
    "SOURCE_USER",
    "SOURCE_SYSTEM",
    "SOURCE_INFERRED",
    "IMPORTANCE_LOW",
    "IMPORTANCE_MEDIUM",
    "IMPORTANCE_HIGH",
    "IMPORTANCE_CRITICAL",
]
