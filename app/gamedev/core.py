"""Engine-Neutral GameCore Contract & Deterministic Execution Pipeline.

Defines the formal contract and pipeline governing all pure game logic in PROFESSOR-J:
- Zero external engine dependencies (strictly pure Python / headless).
- Deterministic state mutation, intent routing, and fixed timestep stepping.
- Snapshotting, SHA-256 state hashing, delta computing, and execution tracing.
- Invariant verification and replay auditing.
"""

from __future__ import annotations

import copy
import logging
from collections.abc import Callable, Sequence
from typing import Any, Protocol, runtime_checkable

from app.domain.gamedev import (
    IntentResult,
    StateDelta,
    StateSnapshot,
    StepResult,
)
from app.gamedev.primitives import ExecutionTracer

logger = logging.getLogger(__name__)


@runtime_checkable
class GameCoreProtocol(Protocol):
    """Formal protocol for engine-neutral pure game logic cores."""

    def initial_state(self) -> dict[str, Any]:
        """Produce the clean initial state for a new game session."""
        ...

    def apply_intent(self, state: dict[str, Any], intent: Any) -> IntentResult:
        """Apply an intent to current state, executing rules and producing new state and events."""
        ...

    def step(self, state: dict[str, Any], dt: float) -> StepResult:
        """Advance time by dt, executing active continuous systems."""
        ...

    def events(self, result: StepResult | IntentResult) -> tuple[Any, ...]:
        """Extract domain events emitted during an execution step or intent."""
        ...

    def snapshot(self, state: dict[str, Any], tick: int = 0) -> StateSnapshot:
        """Create an immutable snapshot of current state."""
        ...

    def restore(self, snapshot: StateSnapshot) -> dict[str, Any]:
        """Restore state dictionary from an immutable snapshot."""
        ...

    def state_hash(self, state: dict[str, Any]) -> str:
        """Compute deterministic SHA-256 hash of state."""
        ...

    def state_delta(
        self,
        previous: dict[str, Any],
        current: dict[str, Any],
        from_tick: int = 0,
        to_tick: int = 1,
    ) -> StateDelta:
        """Compute structured delta difference between two states."""
        ...

    def verify_invariants(self, state: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        """Verify declared domain invariants on state. Returns (is_valid, violations)."""
        ...


class BaseGameCore:
    """Foundational, engine-neutral GameCore implementation with built-in execution pipeline."""

    def __init__(
        self,
        schema_version: int = 1,
        invariants: Sequence[Callable[[dict[str, Any]], tuple[bool, str]]] = (),
    ) -> None:
        self.schema_version = schema_version
        self._invariants = list(invariants)
        self._intent_handlers: dict[
            type, Callable[[dict[str, Any], Any], tuple[bool, list[Any], str | None]]
        ] = {}
        self._step_systems: list[
            Callable[[dict[str, Any], float, int], tuple[list[Any], str | None]]
        ] = []
        self._tick: int = 0
        self._tracer = ExecutionTracer()

    def register_intent_handler(
        self,
        intent_type: type,
        handler: Callable[[dict[str, Any], Any], tuple[bool, list[Any], str | None]],
    ) -> None:
        """Register a handler function for an intent type."""
        self._intent_handlers[intent_type] = handler

    def register_step_system(
        self,
        system: Callable[[dict[str, Any], float, int], tuple[list[Any], str | None]],
    ) -> None:
        """Register a continuous timestep system."""
        self._step_systems.append(system)

    def register_invariant(
        self,
        invariant_fn: Callable[[dict[str, Any]], tuple[bool, str]],
    ) -> None:
        """Register a state invariant validator."""
        self._invariants.append(invariant_fn)

    def initial_state(self) -> dict[str, Any]:
        """Default initial state."""
        return {
            "schema_version": self.schema_version,
            "tick": 0,
            "is_active": True,
        }

    def apply_intent(self, state: dict[str, Any], intent: Any) -> IntentResult:
        """Execute intent through validation -> handler -> invariant check -> state mutation."""
        intent_type = type(intent)
        handler = self._intent_handlers.get(intent_type)
        if not handler:
            return IntentResult(
                success=False,
                new_state=state,
                events=(),
                error=f"Unrecognized intent type: {intent_type.__name__}",
            )

        # Working copy to preserve atomicity on failure
        working_state = copy.deepcopy(state)

        # 1. Execute handler
        try:
            success, events, err = handler(working_state, intent)
        except Exception as exc:
            return IntentResult(
                success=False,
                new_state=state,
                events=(),
                error=f"Handler exception: {exc}",
            )

        if not success:
            return IntentResult(
                success=False,
                new_state=state,
                events=tuple(events),
                error=err or "Intent rejected by domain rule",
            )

        # 2. Invariant verification
        valid, violations = self.verify_invariants(working_state)
        if not valid:
            return IntentResult(
                success=False,
                new_state=state,
                events=(),
                error=f"Invariant violation after intent: {', '.join(violations)}",
            )

        working_state["tick"] = working_state.get("tick", 0) + 1
        return IntentResult(
            success=True,
            new_state=working_state,
            events=tuple(events),
            error=None,
        )

    def step(self, state: dict[str, Any], dt: float) -> StepResult:
        """Advance time by dt through registered continuous systems."""
        working_state = copy.deepcopy(state)
        current_tick = working_state.get("tick", 0) + 1
        working_state["tick"] = current_tick
        emitted_events: list[Any] = []

        for sys in self._step_systems:
            try:
                events, err = sys(working_state, dt, current_tick)
                if events:
                    emitted_events.extend(events)
            except Exception as exc:
                logger.error("Step system failure: %s", exc)

        return StepResult(
            new_state=working_state,
            events=tuple(emitted_events),
            dt=dt,
            tick=current_tick,
        )

    def events(self, result: StepResult | IntentResult) -> tuple[Any, ...]:
        return result.events

    def snapshot(self, state: dict[str, Any], tick: int = 0) -> StateSnapshot:
        current_tick = tick or state.get("tick", 0)
        return self._tracer.create_snapshot(
            tick=current_tick,
            schema_version=self.schema_version,
            state=state,
        )

    def restore(self, snapshot: StateSnapshot) -> dict[str, Any]:
        return copy.deepcopy(snapshot.state_data)

    def state_hash(self, state: dict[str, Any]) -> str:
        return self._tracer.hash_state(state)

    def state_delta(
        self,
        previous: dict[str, Any],
        current: dict[str, Any],
        from_tick: int = 0,
        to_tick: int = 1,
    ) -> StateDelta:
        snap1 = self.snapshot(previous, tick=from_tick)
        snap2 = self.snapshot(current, tick=to_tick)
        return self._tracer.compute_delta(snap1, snap2)

    def verify_invariants(self, state: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        violations: list[str] = []
        for inv_fn in self._invariants:
            try:
                ok, reason = inv_fn(state)
                if not ok:
                    violations.append(reason)
            except Exception as exc:
                violations.append(f"Invariant check error: {exc}")
        return len(violations) == 0, tuple(violations)


__all__ = [
    "GameCoreProtocol",
    "BaseGameCore",
]
