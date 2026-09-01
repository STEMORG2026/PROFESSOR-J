# Presentation Engine Binding & Dual Certification Protocol

## 1. Dual Certification Architecture

PROFESSOR-J enforces a strict two-tier certification gate:

```text
┌─────────────────────────────────────────────────────────────┐
│                 TIER 1: PURE_CORE_CERTIFIED                 │
│  • Domain AST Purity (0 engine imports)                     │
│  • Invariant Preservation on Initial & Stepped States       │
│  • State Hash Determinism & Snapshot Deep-Copy Fidelity     │
│  • Lockstep Replay Verification (0 divergence)              │
│  • Headless Sandbox Test Suite Execution                    │
└──────────────────────────────┬──────────────────────────────┘
                               │ (Prerequisite)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│               TIER 2: ENGINE_BINDING_CERTIFIED              │
│  • Pure Core Certificate Validity (Must be GREEN)           │
│  • Boundary Purity (GameCore has 0 engine types)            │
│  • Input Translation Fidelity (Actions -> Typed Intents)    │
│  • Domain Event Propagation to Visual Presenters            │
│  • State -> View Synchronization Fidelity                   │
│  • Frame-Rate Independence (30/60/120 FPS Invariance)       │
│  • Deterministic Replay through Presentation Runner         │
│  • Presentation Failure Isolation (Crash Containment)       │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Implementing Another Engine Adapter (Godot / Unreal / WebCanvas)

Because the presentation boundary is 100% engine-neutral, implementing a new engine adapter requires only implementing the presentation consumer side:

1. **Implement `GameEngineAdapter`**:
   - Declare `engine_target = EngineTarget.GODOT` (or `UNREAL`, `WEB_CANVAS`).
   - Define project scaffolding rules.
2. **Implement Input Translation**:
   - Map engine-specific inputs (e.g. Godot `InputEventKey`, Web `keydown`) to typed domain intents (e.g. `MoveIntent`, `AttackIntent`).
3. **Implement Event Presenters**:
   - Subscribe to domain events emitted from `PresentationBridge.drain_events()` and route to engine VFX/SFX systems.
4. **Implement State View Synchronization**:
   - Synchronize domain coordinates and attributes into engine nodes/actors/transforms.
5. **Enforce Fixed-Timestep Accumulation**:
   - Drive `bridge.advance_frame(delta)` inside the engine's main loop.
6. **Pass `GameCoreCertifier.certify_engine_binding(...)`**.
