# PROFESSOR-J Versioning

**Version:** 1.0.0
**Status:** Active
**Owner:** Architecture
**Applies To:** This repository (general-purpose autonomous AI platform)
**Related:** `docs/600-changelog.md`, `pyproject.toml`, `docs/WORKING-PROCEDURE.md`,
  workspace `docs/WORKSPACE-VERSIONING.md`

---

## 1. Purpose

PROFESSOR-J tracks a single **repository semantic version** (`VERSION`) as the release
source of truth for the platform, coordinated with `docs/600-changelog.md` entries and the
workspace versioning system. It keeps documentation version markers fresh and gives every
reader a stable reference to a specific platform state.

---

## 2. Source of truth

- **Repository release version:** root `VERSION` (semver, e.g. `1.0.0`).
- **Changelog:** `docs/600-changelog.md` — human-readable, updated per release.
- Python packages / frontend: versioned by their own manifests when shipped; the repo
  `VERSION` documents the aggregate platform release.

---

## 3. Bumping rules

Semver `X.Y.Z`:
- **MAJOR** — breaking change to the platform contract / public API / migration surface.
- **MINOR** — new capability, phase, or backwards-compatible feature.
- **PATCH** — critical fix to build, CI, governance, or a small corrective change.

Bump and keep docs in sync with the workspace tool:

```bash
python3 ../scripts/version_bump.py bump minor --scope PROFESSOR-J   # 1.0.0 -> 1.1.0
python3 ../scripts/version_bump.py check --scope PROFESSOR-J        # must exit 0
```

Conventional commit types (`feat|fix|docs|chore|refactor`, …) plus a `docs/600-changelog.md`
entry accompany every release.

---

## 4. Enforcement

- The workspace pre-commit `check-doc-versions` / CI mirror verifies `**Version:**` doc
  markers match `VERSION` before merge.
- `docs/600-changelog.md` is updated in the same release PR; a release without a changelog
  entry is rejected by review discipline.
- This repository's own governance (`AGENTS.md`, `docs/GOVERNANCE.md`, `docs/RULES.md`)
  overrides workspace defaults inside this repo, and is not weakened here.

---

## 5. Scope

The platform repository, phases, and shipped packages follow this convention. Deferred:
per-package semantic-version manifests until a release pipeline exists (documented in
`IMPLEMENTATION-PLAN.md`).

---

*Derived from workspace `docs/WORKSPACE-VERSIONING.md`.*
