# GameCore Formal Interface Contract

## Overview

The `GameCoreProtocol` defines the authoritative, engine-neutral contract that every game logic module must implement to interface with headless test runners, property fuzzer, deterministic replayer, and downstream presentation adapters.

## Interface Definition

```python
class GameCoreProtocol(Protocol):
    def initial_state(self) -> dict[str, Any]:
        """Return the initial default state dictionary."""
        ...

    def apply_intent(self, state: dict[str, Any], intent: Any) -> IntentResult:
        """Apply a player or AI input intent deterministically."""
        ...

    def step(self, state: dict[str, Any], dt: float) -> StepResult:
        """Advance game simulation by continuous timestep dt."""
        ...

    def events(self, result: IntentResult | StepResult) -> tuple[Any, ...]:
        """Extract emitted domain events."""
        ...

    def snapshot(self, state: dict[str, Any], tick: int = 0) -> GameSnapshot:
        """Serialize state into an immutable snapshot."""
        ...

    def restore(self, snapshot: GameSnapshot) -> dict[str, Any]:
        """Restore state from snapshot."""
        ...

    def state_hash(self, state: dict[str, Any]) -> str:
        """Calculate canonical SHA-256 hash of state dictionary."""
        ...

    def state_delta(self, previous_state: dict[str, Any], current_state: dict[str, Any]) -> dict[str, Any]:
        """Calculate shallow diff between two states."""
        ...

    def verify_invariants(self, state: dict[str, Any]) -> tuple[bool, list[str]]:
        """Verify all registered domain invariants against state."""
        ...
```

## Result Types

### `IntentResult`
- `success: bool` — Whether intent executed cleanly without violating invariants.
- `new_state: dict[str, Any]` — State after intent application.
- `events: tuple[Any, ...]` — Domain events emitted during dispatch.
- `error: str | None` — Failure or invariant violation message.
- `metadata: dict[str, Any]` — Additional telemetry.

### `StepResult`
- `new_state: dict[str, Any]` — State after time step integration.
- `events: tuple[Any, ...]` — Domain events emitted during tick.
- `dt: float` — Delta time integrated.
- `tick: int` — Monotonic simulation tick count.
- `metadata: dict[str, Any]` — Additional step metrics.
