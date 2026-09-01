"""Durable memory store — low-level CRUD + atomic JSON persistence.

Pattern-inherited from JARVIS ``app/memory/store.py``. Holds a list of
:class:`~app.memory.schema.Memory` records, persists to a single JSON file with
atomic (temp-file + ``os.replace``) writes, and validates field updates so a bad
caller (or model) can never corrupt a memory's invariants.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, get_type_hints

from app.memory.schema import (
    Memory,
)

logger = logging.getLogger(__name__)

_TYPE_HINTS = get_type_hints(Memory)
# Fields that identify a memory or record its creation. Never mutate after creation:
# changing `id` would orphan the memory and break retrieval/delete by ID.
_IMMUTABLE_FIELDS = {"id", "created_at"}

_FORMAT_VERSION = "2.0"


def _validate_field_value(key: str, value: Any) -> Any:
    """Validate + coerce a value destined for a Memory field.

    Raises :class:`ValueError` if the field is unknown, immutable, or the value
    is the wrong type/out of range.
    """
    if key not in _TYPE_HINTS:
        raise ValueError(f"unknown field {key!r}")
    if key in _IMMUTABLE_FIELDS:
        raise ValueError(f"field {key!r} is immutable and cannot be updated")

    expected = _TYPE_HINTS[key]

    if expected is float:
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"field {key!r} must be a number, got {value!r}") from None
        if key in ("confidence", "importance") and not (0.0 <= float(value) <= 1.0):
            raise ValueError(f"field {key!r} must be between 0.0 and 1.0")
    elif expected is int:
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"field {key!r} must be an integer, got {value!r}") from None
        if key == "access_count" and int(value) < 0:
            raise ValueError(f"field {key!r} must be >= 0")
    elif expected is str:
        if value is None:
            raise ValueError(f"field {key!r} must not be None")
        value = str(value)
    elif expected is dict:
        if not isinstance(value, dict):
            raise ValueError(f"field {key!r} must be a dict")
    return value


class MemoryStore:
    """Low-level storage of :class:`Memory` records with durable persistence."""

    def __init__(self, path: str | Path | None = None) -> None:
        if path is None:
            # Scratch JSON file (tests/dev) when no durable path is configured.
            import tempfile

            tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
            tmp.close()
            path = tmp.name
        self.path = Path(path)
        self._memories: list[Memory] = []
        self._dirty = False
        self._load()

    # ── CRUD ──────────────────────────────────────────────────────────────
    def add(self, memory: Memory) -> Memory:
        self._memories.append(memory)
        self._dirty = True
        return memory

    def get_by_id(self, memory_id: str) -> Memory | None:
        for m in self._memories:
            if m.id == memory_id:
                return m
        return None

    def find_by_category_and_type(self, category: str, memory_type: str) -> list[Memory]:
        return [
            m for m in self._memories if m.category == category and m.memory_type == memory_type
        ]

    def get_all(self) -> list[Memory]:
        return list(self._memories)

    def update_fields(self, memory_id: str, updates: dict[str, Any]) -> Memory | None:
        """Validate and apply field updates; skip bad values with a warning."""
        memory = self.get_by_id(memory_id)
        if not memory:
            return None
        for key, value in updates.items():
            try:
                validated = _validate_field_value(key, value)
            except ValueError as exc:
                logger.warning(
                    "Skipping invalid update to memory %s field %r: %s", memory_id, key, exc
                )
                continue
            setattr(memory, key, validated)
        memory.mark_updated()
        self._dirty = True
        return memory

    def remove(self, memory_id: str) -> Memory | None:
        for i, m in enumerate(self._memories):
            if m.id == memory_id:
                removed = self._memories.pop(i)
                self._dirty = True
                return removed
        return None

    def remove_by_category_and_type(self, category: str, memory_type: str) -> list[Memory]:
        to_remove = self.find_by_category_and_type(category, memory_type)
        for m in to_remove:
            self._memories.remove(m)
        if to_remove:
            self._dirty = True
        return to_remove

    def count(self) -> int:
        return len(self._memories)

    def clear(self) -> None:
        self._memories.clear()
        self._dirty = True
        self.save()

    # ── Persistence ───────────────────────────────────────────────────────
    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def save(self) -> None:
        """Persist to disk atomically and durably (unless already clean)."""
        if not self._dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"version": _FORMAT_VERSION, "memories": [m.to_dict() for m in self._memories]}

        tmp_path = self.path.with_name(f"{self.path.name}.tmp.{os.getpid()}")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.path)
            self._dirty = False
        except BaseException:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
            raise

    def save_if_dirty(self) -> None:
        self.save()

    def force_save(self) -> None:
        self._dirty = True
        self.save()

    # ── Loading ───────────────────────────────────────────────────────────
    def _load(self) -> None:
        self._memories = []
        self._dirty = False
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            self._quarantine_and_warn(str(exc))
            return
        memories, had_bad = self._deserialize(data)
        self._memories = memories
        if had_bad:
            self._dirty = True

    def _quarantine_and_warn(self, reason: str) -> None:
        """Preserve a corrupt file's bytes so the next save can't destroy it."""
        backup = self.path.with_name(f"{self.path.name}.corrupt-{int(os.getpid())}")
        try:
            os.replace(self.path, backup)
            logger.warning(
                "Quarantined corrupt memory file %s -> %s (%s)", self.path, backup, reason
            )
        except OSError:
            logger.warning(
                "Corrupt memory file %s could not be quarantined (%s)", self.path, reason
            )

    @staticmethod
    def _deserialize(data: Any) -> tuple[list[Memory], bool]:
        """Parse JSON into Memory objects; skip malformed records, never wipe all."""
        if isinstance(data, dict) and "version" in data:
            raw = data.get("memories", [])
        elif isinstance(data, dict) and "facts" in data:
            raw = data["facts"]  # legacy JARVIS-style shape
        elif isinstance(data, list):
            logger.warning("Memory file contained a bare list; treating as empty.")
            return [], False
        else:
            logger.warning("Unrecognized memory file structure; treating as empty.")
            return [], False

        memories: list[Memory] = []
        bad = 0
        for record in raw:
            if not isinstance(record, dict):
                bad += 1
                continue
            try:
                memories.append(Memory.from_dict(record))
            except (KeyError, TypeError, ValueError) as exc:
                bad += 1
                logger.warning("Skipping malformed memory record: %s", exc)
        if bad:
            logger.warning("Dropped %d malformed memory record(s).", bad)
        return memories, bad > 0


__all__ = ["MemoryStore"]
