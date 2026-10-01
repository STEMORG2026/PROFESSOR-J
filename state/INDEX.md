# INDEX — Session Log

> Searchable history. One row per completed session. Search by keyword or path before reading
> session files — do not read them all.

| Session ID | Agent | Date (UTC) | Title | Files touched | Status | Branch |
|---|---|---|---|---|---|---|
| 20261001-1209-A7F3 | A7F3 | 2026-10-01 | Bootstrap MACP; MACP v2 amendment; docs-governance reconciliation; CI mirror 12/14 → 13/14 | `state/**`, `requirements.txt`, `docs.manifest.yaml`, `scripts/docs/*`, `scripts/declared_defects.py`, `AGENTS.md`, `docs/500`, `docs/700`, `githooks/pre-push`, `tests/meta/`, `tests/unit/knowledge/test_lhs_adapter.py` | **PARTIAL** (B3 needs human) | `fix/containment-48h` |

## Search guidance

- Enforcement / gate → `scripts/ci_gate.py`, `githooks/pre-push`
- Documentation governance → `docs.manifest.yaml`, `scripts/docs/`
- CI / workflow failures → `.github/workflows/`, PR #129
- Dependencies → `requirements.txt`, `docs/201-constraints.md`
