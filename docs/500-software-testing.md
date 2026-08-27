# Testing Strategy

> Companion: `software-testing` v0.1.0 from ProjectTemplates 0.1.0
> Answers here are this project's source of truth.
> Re-generate or adopt a newer template only as a deliberate decision (`tpl update`).

---

## Test levels and emphasis

| Level | Emphasis | Coverage target |
|-------|----------|-----------------|
| Unit (domain) | Rule/logic correctness, purity, determinism | ≥ 95% |
| Unit (brain/agents) | Socratic flow, evaluation, tool dispatch | ≥ 95% |
| Integration (adapters) | REST/SSE/WS contracts, auth, persistence | ≥ 85% |
| Sandbox security | Escape attempts, timeouts, resource caps | High (security-critical) |
| E2E (frontend) | Streaming render, voice smoke | Representative paths (Playwright, Phase 9) |
| Fault injection | Circuit-breaker failover, provider 429/503 | Deterministic scenarios |

## Priority of what must be tested vs light coverage

- **Must:** domain rules, safety gates, sandbox isolation, grounding/citation audits,
  circuit-breaker failover.
- **Light:** visual/styling details, non-critical config paths.

## Environments, fixtures, repeatability

- pytest with deterministic fixtures; seeded RNG where relevant; mock provider pool;
  fake LHS export fixture; CI runs everything fresh.

## Commands to run each level

```bash
.venv/bin/python -m pytest tests/             # all backend levels
.venv/bin/mypy app/                           # strict typecheck
.venv/bin/pre-commit run --all-files          # ruff, ruff-format, mypy, eof fixes
# frontend (Phase 7+, once `frontend/` exists): cd frontend && pnpm typecheck && pnpm lint
# Playwright E2E added in Phase 9
```

## Interpretation: code bug vs design bug

- A failing unit test in `app/domain/` = logic bug → fix code.
- A failing boundary/import check = layering violation → fix structure (or record ADR).
- A failing contract test against LHS export = schema drift → adapter fix, do not touch
  the canonical source.
- A test that is flaky/timing-dependent in E2E mode = design bug in test isolation.
