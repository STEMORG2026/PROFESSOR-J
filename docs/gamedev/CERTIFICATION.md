# GameCore Formal Certification Standard

## Overview

The `GameCoreCertifier` conducts formal static and dynamic audits on developed GameCore projects before presentation engine binding.

## Certification Gates

A GameCore is certified (`certified == True`) if and only if all of the following conditions pass:

1. **Domain Purity**: Zero imports of `UnityEngine`, `Godot`, `Unreal`, `pygame`, or platform internal modules (`app.tools`, `app.db`, etc.) across all source files.
2. **Syntax and Typing**: All Python files parse cleanly via `ast.parse`.
3. **Invariants**: `core.verify_invariants(initial_state)` returns zero violations.
4. **State Hash Determinism**: Multiple snapshot hashes of identical states match.
5. **Snapshot Fidelity**: Mutating a restored state dictionary does not alter the historical snapshot.
6. **Deterministic Replay**: Recording a session and verifying it completes with zero hash divergences.
7. **Sandbox Execution**: Headless test suite passes 100% inside `CodeSandbox`.
8. **Protected Integrity**: Zero test or governance files were modified.
