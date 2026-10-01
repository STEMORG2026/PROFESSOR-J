# INDEX — Session Log

> Searchable history. One row per completed session. Search by keyword or path before reading
> session files — do not read them all.

| Session ID | Agent | Date (UTC) | Title | Files touched | Status | Branch |
|---|---|---|---|---|---|---|
| 20261001-1209-A7F3 | A7F3 | 2026-10-01 | Bootstrap MACP + repository audit | `state/**` | IN-PROGRESS | `fix/containment-48h` |

## Search guidance

- Enforcement / gate → `scripts/ci_gate.py`, `githooks/pre-push`
- Documentation governance → `docs.manifest.yaml`, `scripts/docs/`
- CI / workflow failures → `.github/workflows/`, PR #129
- Dependencies → `requirements.txt`, `docs/201-constraints.md`
