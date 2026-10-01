# REGISTRY — Active Agents

> Claim ownership before modifying files. Release claims at shutdown.
> Owner INACTIVE if their session file has had no update in >24h — you may then take over.

| Agent ID | Type | Branch | Task (one line) | Started (UTC) | Status | Claims (files/dirs) |
|---|---|---|---|---|---|---|
| A7F3 | DeepSeek v4.1 Flash (DSH) | `fix/containment-48h` | Bootstrap MACP; green the CI mirror; reconcile `state/` with docs governance | 2026-10-01T12:09Z | **PARTIAL** (released) | none — all claims released at shutdown |

## Coordination notes

- `state/` is created by A7F3 and owned by whichever agent is reconciling. Multiple agents may
  append to `state/sessions/` and `state/plans/` freely; only the reconciler rewrites
  `DASHBOARD.md`, `REGISTRY.md`, `INDEX.md`.
- No other agent is active at bootstrap time.

## Convention

- Agent ID: 4 alphanumeric characters, invented by the agent (e.g. `A7F3`).
- One session file per agent per session: `state/sessions/YYYYMMDD-HHMM-<ID>-<slug>.md`.
