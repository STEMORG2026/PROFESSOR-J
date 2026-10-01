# ARCHITECTURE — Current Reality

> Living document. Describes what IS, not what is planned. Update when structure changes.
> **Last verified:** 2026-10-01 against `fix/containment-48h` @ `164d631`.

## Stack

| Layer | Technology | Version note |
|---|---|---|
| Language | Python | targets **3.11+**; local dev venv is **3.14.7** (see DEBT D1) |
| Web | FastAPI + Uvicorn | `>=0.54.0` |
| Validation | Pydantic / pydantic-settings | `==2.13.5` |
| Orchestration | LangGraph | `>=1.2.11` |
| Memory | ChromaDB + BM25 | `>=1.5.9` |
| Telemetry | OpenTelemetry + Langfuse | OTel trio pinned in lockstep at 1.45.0 |
| Frontend | Next.js 15 / React 19 | `frontend/` present (Phase 7+) |
| Tests | pytest + pytest-asyncio + pytest-cov | `asyncio_mode = "auto"` |
| Quality | ruff · mypy (strict) · pre-commit | CI pins ruff 0.6.9, mypy 1.14.1, pre-commit 4.0.1 |

## Layered boundaries (inviolable)

```
app/domain/     pure dataclasses. NO imports from adapters/brain/db/frameworks.
app/brain/      async execution loops. NEVER imports web framework objects.
app/adapters/   HTTP/ingress boundary.
app/tools/      tool execution — MUST pass through the safety gate.
```

## Entry points & topology

- `app/main.py` — FastAPI app; calls `setup_logging()` before serving.
- `app/bootstrap.py` — builds `AppRoot`; wires ~30 subsystems. **Note:** `web`, `browser`,
  `computer_use` are constructed (lines ~250) and attached to `AppRoot` (lines ~283) but are **not
  registered with `ToolExecutor`** — a latent safety-gate bypass (see DEBT D4).
- `app/guardrails/policy.py:92` — `@safety_gate(tier, description, policy)` decorator.
  `ToolExecutor.register_fn(name, fn, tier=...)` is the registration-based gate; both route
  through `SafetyPolicy`.
- `app/adapters/auth.py` — **single ingress boundary**: `require_api_key` (fails closed, rejects
  placeholder tokens) and `resolve_base_url` (egress allow-list). Added after audit S0-1/S0-2.

## Enforcement architecture (the important part)

Enforcement is **local-first**, because GitHub could not block merges historically:

```
githooks/pre-push  →  scripts/ci_gate.py (14 stages, no bypass flag)
                   →  scripts/verify_repeat.py --runs 3 --control
CI: .github/workflows/gate-mirror.yml replays the SAME entry point (a mirror, not the gate)
```

Documentation is a **gated surface**: `docs.manifest.yaml` classifies every markdown file exactly
once; 5 checkers under `scripts/docs/` are wired into the gate.

## CI/CD

| Workflow | Trigger | Purpose |
|---|---|---|
| `ci.yml` | push/PR → main | 8 jobs (lint, test, security, board, docs, frontend, branching, commitlint) |
| `gate-mirror.yml` | push → main, PR, manual | replays the local gate on a clean runner |
| `quality-ratchets.yml` | nightly 03:17 UTC | mutation, whole-suite coverage, repair-benchmark rate |
| `release.yml` | tags `v*` | release |
| `dependabot-auto-merge.yml` | PR by dependabot | approve + enable auto-merge |

**Ruleset `main`** (branch, `~DEFAULT_BRANCH`): `deletion`, `non_fast_forward`, `pull_request`
(0 approvals), `required_linear_history`, and `required_status_checks` requiring exactly
`Local gate, replayed on a clean runner` and `Documentation gate (explicit, non-skippable)`.
`bypass_actors: []`. **Currently `enforcement: evaluate`.**
