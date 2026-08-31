# Cognitive Repair Protocol & Invariant Preservation

## Overview

The `CognitiveRepairEngine` and `RepairCoordinator` provide autonomous diagnose -> propose -> validate -> atomic patch -> verify capabilities for game logic projects.

## Scope Classification

Files in a project are strictly classified into modification scopes:
- `ModificationScope.IMPLEMENTATION` — **Mutable**. Eligible for automated repair patches.
- `ModificationScope.TEST` — **Immutable**. Preserved byte-for-byte; test modifications are strictly rejected.
- `ModificationScope.GOVERNANCE` — **Immutable**. `AGENTS.md`, `CONSTITUTION.md`, `.agents/` rules cannot be touched.
- `ModificationScope.CONFIGURATION` — **Immutable**. `pyproject.toml`, `package.json`, `.csproj` cannot be touched.
- `ModificationScope.FRAMEWORK` — **Immutable**. Core capability source files cannot be patched by project repairs.

## Multi-File Transactional Atomicity

When a defect requires coordinated changes across multiple files:
1. All target files are checked against modification scope.
2. Original contents are snapshotted in memory.
3. Patches are simulated in pending memory buffers.
4. Each patched file is validated using Python's `ast.parse` and `ASTPatchValidator` (rejecting syntax errors and forbidden engine imports).
5. If any validation fails, zero files are written to disk.
6. If all validations succeed, files are written atomically.
7. Protected file hashes are verified to ensure zero collateral modification.
