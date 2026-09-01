# UnityEngineAdapter & Presentation Architecture

## 1. Overview & One-Way Dependency Rule

The `UnityEngineAdapter` connects the engine-neutral PROFESSOR-J `GameCore` with a Unity presentation client.

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                           CognitiveBrain                                │
│                   (Intent Analysis & Orchestration)                     │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            GameDevAgent                                 │
│  ┌─────────────────────────┐             ┌───────────────────────────┐  │
│  │   SystemSynthesizer     │             │    CognitiveRepairEngine  │  │
│  │ (Manifest & Code Gen)   │             │ (Multi-File AST Repair)   │  │
│  └───────────┬─────────────┘             └─────────────▲─────────────┘  │
│              │                                         │                │
│              ▼                                         │ Telemetry      │
│  ┌─────────────────────────────────────────────────────┴─────────────┐  │
│  │                     Certified Pure GameCore                       │  │
│  │  • Pure Domain State Schema     • Invariant Checks                │  │
│  │  • Intent Dispatch Handlers     • Continuous Step Integration     │  │
│  │  • Snapshot / Restore           • State Hashing & Delta Calc      │  │
│  └───────────────────────────┬───────────────────────────────────────┘  │
└────────────────────────────────────┼────────────────────────────────────┘
                                     │ (100% Pure Boundary)
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       Presentation Contract                             │
│       (PresentationAdapterProtocol, PresentationBridge, Intents)        │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         UnityEngineAdapter                              │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                   Unity Presentation Layer                        │  │
│  │  • UnityGameRunner (Fixed-Timestep Simulation Driver)             │  │
│  │  • CoreBridge (Domain Event Sinks & UnityEvent Dispatch)          │  │
│  │  • UnityInputAdapter (Engine Key/Axis -> Domain Intent Factory)   │  │
│  │  • UnityStatePresenter (State Snapshot -> Transform/View Sync)    │  │
│  │  • UnityEntityView (GameObjects, Meshes, Animator Triggers)       │  │
│  │  • UnityHUDView (UI Healthbars, AP Counters, Combat Text)         │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Invariants:
1. **GameCore = Truth**: State, rules, intents, health, victory/defeat, collision decisions, and random seed streams are strictly owned by GameCore.
2. **Unity = Representation**: Transforms, GameObject lifecycle, Mecanim triggers, VFX, SFX, and UI display are owned by Unity.
3. **One-Way Direction**: Unity depends on GameCore and Presentation Contract; GameCore **NEVER** imports `UnityEngine`.

---

## 2. Project Hierarchy Scaffolding

```text
Unity/
├── Assets/
│   ├── Scripts/
│   │   ├── Domain/                 <-- Pure C# Domain (0 UnityEngine imports)
│   │   │   ├── Contracts.cs
│   │   │   └── GameCore.Domain.csproj
│   │   ├── CoreBridge/             <-- Event Sinks & Presentation Bridges
│   │   │   └── CoreBridge.cs
│   │   ├── Presentation/           <-- Presentation Views & Runners
│   │   │   ├── UnityGameRunner.cs
│   │   │   ├── UnityEntityView.cs
│   │   │   └── UnityStatePresenter.cs
│   │   ├── Input/                  <-- Input Translation
│   │   │   └── UnityInputAdapter.cs
│   │   └── UI/                     <-- HUD & Menus
│   │       └── UnityHUDView.cs
│   └── Scenes/
│       └── MainScene.unity
└── Tests/
    ├── EditMode/
    │   └── DomainTests.cs
    └── GameCore.Tests.csproj
```

---

## 3. Frame-Rate Independence & Fixed-Step Timing

Unity `Update()` frame intervals vary based on hardware load (e.g. 30 FPS vs 60 FPS vs 144 FPS).
To ensure determinism, `PresentationBridge` maintains a fixed-step accumulator:

```csharp
private float _accumulator = 0f;
private const float FixedTimestep = 1f / 60f;

private void Update()
{
    _accumulator += Time.deltaTime;
    while (_accumulator >= FixedTimestep)
    {
        _core.Step(FixedTimestep);
        _accumulator -= FixedTimestep;
    }
    _presenter.SyncState(_core.CurrentState);
}
```

The authoritative simulation output and state hash are **100% invariant** to presentation frame schedules.
