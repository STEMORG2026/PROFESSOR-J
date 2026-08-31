"""Universal Game Engineering Primitives for PROFESSOR-J.

Provides foundational, engine-agnostic primitives required across diverse game genres:
- FlowResource (Continuous & discrete capacity/consumption/regeneration)
- ContinuousSpace2D & BoundingBox2D (Continuous spatial geometry & AABB collision)
- SeededPRNGStream (Hierarchical deterministic seed splitting & stream isolation)
- ExecutionTracer (Deterministic state snapshotting, delta tracking & replay verification)

Invariants:
- Pure Python 3.11+; zero external rendering/engine dependencies.
- 100% deterministic and reproducible across seeds and execution platforms.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, TypeVar

from app.domain.gamedev import ExecutionTrace, StateDelta, StateSnapshot

T = TypeVar("T")


# ──────────────────────────────────────────────────────────────────────────────
# 1. FlowResource (Universal Resource & Economy Primitive)
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class FlowResource:
    """Universal game resource primitive representing health, mana, gold, stamina, etc."""

    name: str
    value: float
    min_value: float = 0.0
    max_value: float = 100.0
    regen_rate: float = 0.0  # Units gained per second / tick

    def __post_init__(self) -> None:
        if self.min_value > self.max_value:
            raise ValueError(
                f"min_value ({self.min_value}) cannot exceed max_value ({self.max_value})"
            )
        self.value = max(self.min_value, min(self.value, self.max_value))

    def consume(self, amount: float) -> bool:
        """Consume resource if sufficient balance is available. Returns True on success."""
        if amount < 0:
            raise ValueError("Consumed amount must be non-negative")
        if self.value - amount < self.min_value:
            return False
        self.value -= amount
        return True

    def produce(self, amount: float) -> float:
        """Add resource up to max_value cap. Returns actual amount added."""
        if amount < 0:
            raise ValueError("Produced amount must be non-negative")
        prev = self.value
        self.value = min(self.max_value, self.value + amount)
        return self.value - prev

    def tick(self, dt: float = 1.0) -> float:
        """Advance time by dt and apply regeneration. Returns new value."""
        if self.regen_rate > 0:
            self.produce(self.regen_rate * dt)
        elif self.regen_rate < 0:
            self.consume(-self.regen_rate * dt)
        return self.value

    def set_value(self, new_val: float) -> float:
        """Clamp and set new value."""
        self.value = max(self.min_value, min(new_val, self.max_value))
        return self.value

    @property
    def is_empty(self) -> bool:
        return self.value <= self.min_value

    @property
    def is_full(self) -> bool:
        return self.value >= self.max_value

    @property
    def ratio(self) -> float:
        span = self.max_value - self.min_value
        return (self.value - self.min_value) / span if span > 0 else 0.0


# ──────────────────────────────────────────────────────────────────────────────
# 2. ContinuousSpace2D & BoundingBox2D (Continuous Geometry Primitive)
# ──────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class BoundingBox2D:
    """Axis-Aligned Bounding Box (AABB) in continuous 2D space."""

    x: float
    y: float
    width: float
    height: float

    @property
    def x_min(self) -> float:
        return self.x

    @property
    def x_max(self) -> float:
        return self.x + self.width

    @property
    def y_min(self) -> float:
        return self.y

    @property
    def y_max(self) -> float:
        return self.y + self.height

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.width / 2.0, self.y + self.height / 2.0)

    def intersects(self, other: BoundingBox2D) -> bool:
        """Evaluate if two AABB bounding boxes intersect."""
        return not (
            self.x_max <= other.x_min
            or self.x_min >= other.x_max
            or self.y_max <= other.y_min
            or self.y_min >= other.y_max
        )

    def contains_point(self, px: float, py: float) -> bool:
        """Evaluate if point (px, py) lies within bounding box."""
        return self.x_min <= px <= self.x_max and self.y_min <= py <= self.y_max

    def distance_to(self, other: BoundingBox2D) -> float:
        """Euclidean distance between center points."""
        cx1, cy1 = self.center
        cx2, cy2 = other.center
        return math.hypot(cx2 - cx1, cy2 - cy1)


@dataclass(frozen=True, slots=True)
class ContinuousSpace2D:
    """Continuous 2D boundary space."""

    width: float
    height: float

    def clamp_position(self, x: float, y: float) -> tuple[float, float]:
        """Clamp coordinate point to space boundaries."""
        return (max(0.0, min(x, self.width)), max(0.0, min(y, self.height)))

    def is_inside(self, x: float, y: float) -> bool:
        """Check if coordinate is strictly inside space."""
        return 0.0 <= x <= self.width and 0.0 <= y <= self.height


# ──────────────────────────────────────────────────────────────────────────────
# 3. SeededPRNGStream (Hierarchical Deterministic Seed Splitting)
# ──────────────────────────────────────────────────────────────────────────────
class SeededPRNGStream:
    """Hierarchical deterministic PRNG stream with stream isolation.

    Guarantee: Drawing random values from a child stream (e.g. 'cosmetic') never
    advances or mutates the sequence of sibling streams (e.g. 'gameplay' or 'ai').
    """

    def __init__(self, seed: int, stream_name: str = "root") -> None:
        self.seed = seed
        self.stream_name = stream_name
        self._rng = random.Random(seed)
        self._draw_count = 0

    def split(self, child_name: str) -> SeededPRNGStream:
        """Deterministically derive an isolated child PRNG stream."""
        raw_key = f"{self.seed}:{self.stream_name}->{child_name}"
        derived_seed = int(hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:8], 16)
        return SeededPRNGStream(seed=derived_seed, stream_name=f"{self.stream_name}.{child_name}")

    def randint(self, a: int, b: int) -> int:
        """Generate deterministic integer in [a, b]."""
        self._draw_count += 1
        return self._rng.randint(a, b)

    def random(self) -> float:
        """Generate deterministic float in [0.0, 1.0)."""
        self._draw_count += 1
        return self._rng.random()

    def choice(self, seq: Sequence[T]) -> T:
        """Deterministically choose an item from sequence."""
        if not seq:
            raise IndexError("Cannot choose from empty sequence")
        idx = self.randint(0, len(seq) - 1)
        return seq[idx]


# ──────────────────────────────────────────────────────────────────────────────
# 4. ExecutionTracer (Deterministic Tracing & Replay Verification)
# ──────────────────────────────────────────────────────────────────────────────
class ExecutionTracer:
    """Manages state snapshotting, delta tracking, and deterministic replay auditing."""

    @staticmethod
    def hash_state(state: dict[str, Any]) -> str:
        """Compute deterministic SHA-256 hash of a state dictionary."""
        serialized = json.dumps(state, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def create_snapshot(
        cls,
        tick: int,
        schema_version: int,
        state: dict[str, Any],
        snapshot_id: str = "",
    ) -> StateSnapshot:
        """Create an immutable state snapshot."""
        s_id = snapshot_id or f"snap_{tick}_{schema_version}"
        s_hash = cls.hash_state(state)
        return StateSnapshot(
            snapshot_id=s_id,
            tick=tick,
            schema_version=schema_version,
            state_data=dict(state),
            state_hash=s_hash,
        )

    @classmethod
    def compute_delta(cls, snap1: StateSnapshot, snap2: StateSnapshot) -> StateDelta:
        """Calculate state delta between two snapshots."""
        d1 = snap1.state_data
        d2 = snap2.state_data

        changed: dict[str, Any] = {}
        added: dict[str, Any] = {}
        removed: list[str] = []

        for k, v in d2.items():
            if k not in d1:
                added[k] = v
            elif d1[k] != v:
                changed[k] = v

        for k in d1:
            if k not in d2:
                removed.append(k)

        return StateDelta(
            from_tick=snap1.tick,
            to_tick=snap2.tick,
            changed_fields=changed,
            added_fields=added,
            removed_fields=tuple(sorted(removed)),
        )

    @classmethod
    def record_trace(
        cls,
        tick: int,
        intent_name: str,
        intent_payload: dict[str, Any],
        pre_state: dict[str, Any],
        post_state: dict[str, Any],
        events: tuple[str, ...],
        seed: int = 0,
        success: bool = True,
        error: str | None = None,
    ) -> ExecutionTrace:
        """Record an execution step trace."""
        trace_id = f"trace_t{tick}_{intent_name}"
        return ExecutionTrace(
            trace_id=trace_id,
            seed=seed,
            tick=tick,
            intent_name=intent_name,
            intent_payload=dict(intent_payload),
            pre_state_hash=cls.hash_state(pre_state),
            post_state_hash=cls.hash_state(post_state),
            events_emitted=events,
            success=success,
            error=error,
        )


__all__ = [
    "FlowResource",
    "BoundingBox2D",
    "ContinuousSpace2D",
    "SeededPRNGStream",
    "ExecutionTracer",
]
