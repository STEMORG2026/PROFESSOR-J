# Game System Synthesis Protocol

## Overview

The `SystemSynthesizer` generates complete novel domain subsystems, domain contracts (Intents, Events, State Schema), pure domain implementations, unit/invariant test suites, and a machine-readable `SynthesisManifest`.

## Synthesis Artifact: `SynthesisManifest`

Every synthesized subsystem produces a manifest capturing:
- `manifest_id`: Unique identifier.
- `title`: System title.
- `genre`: Game genre.
- `project_model`: Detected models, states, intents, events, and file scopes.
- `state_schema`: Field definitions, types, and defaults.
- `intent_definitions`: Tuple of declared input intent classes.
- `event_definitions`: Tuple of emitted domain events.
- `system_definitions`: Subsystem class names.
- `dependency_graph`: Intersystem dependency map.
- `invariant_set`: Declared mathematical and domain invariants.
- `execution_model`: Command dispatch and simulation model.
- `test_plan`: Declared automated test cases.
- `verification_plan`: Sandbox execution, AST purity audit, and deterministic replay checks.

## Generation Invariants

1. Implementation code must be placed under `systems/` or `domain/`.
2. Test code must be placed under `tests/`.
3. Code must contain 100% type annotations.
4. Zero presentation or game engine imports are permitted.
