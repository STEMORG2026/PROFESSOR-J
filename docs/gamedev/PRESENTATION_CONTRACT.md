# Presentation Contract & Synchronization Protocol

## 1. Responsibilities Breakdown

| Responsibility | GameCore (Domain Truth) | Presentation Layer (Unity / View) |
|---|---|---|
| **Authoritative State** | ✅ Sole owner of all domain data | ❌ Views are read-only reflections |
| **Game Rules & Logic** | ✅ Pure calculations & invariants | ❌ Zero game outcome logic |
| **Intent Processing** | ✅ Evaluates & validates intents | ❌ Emits raw inputs only |
| **Event Generation** | ✅ Dispatches domain events | ❌ Consumes & visualizes events |
| **Transform & Meshes** | ❌ Zero knowledge of 3D engines | ✅ Owns GameObjects, Meshes, VFX |
| **Animations & Audio** | ❌ Pure abstract event names | ✅ Mecanim triggers, AudioSources |
| **Simulation Timing** | ✅ Fixed timestep calculation | ❌ Frame rate only drives render |

---

## 2. Interface Contracts

### `PresentationAdapterProtocol`
```python
class PresentationAdapterProtocol(Protocol):
    def observe_state(self, state: dict[str, Any]) -> None: ...
    def submit_intent(self, intent: Any) -> IntentResult: ...
    def poll_events(self) -> list[Any]: ...
    def drive_tick(self, dt: float) -> StepResult: ...
```

### `PresentationBridge`
```python
class PresentationBridge:
    def __init__(self, core: GameCoreProtocol, fixed_dt: float = 1.0 / 60.0): ...
    def submit_intent(self, intent: Any) -> IntentResult: ...
    def advance_time(self, dt: float) -> StepResult: ...
    def advance_frame(self, frame_dt: float) -> list[StepResult]: ...
    def drain_events(self) -> list[Any]: ...
    def snapshot(self, tick: int = 0) -> Any: ...
    def restore(self, snapshot: Any) -> None: ...
```

---

## 3. Serialization & Cross-Process Isolation

When GameCore and Unity run across language or process boundaries:
1. **Intents** serialize as JSON envelopes: `{"intent_type": "MoveIntent", "payload": {"unit_id": "p1", "target_x": 2, "target_y": 3}}`.
2. **State Snapshots** serialize as typed dictionaries with monotonic ticks and SHA-256 state hashes.
3. **Domain Events** serialize as strongly-typed event streams: `[{"event_type": "UnitMovedEvent", "data": {...}}]`.
4. Any presentation deserialization failure or render exception is isolated and fail-safe, preserving GameCore integrity.
