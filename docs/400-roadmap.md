# Roadmap & Lifecycle

> Companion: `roadmap` v0.1.0 from ProjectTemplates 0.1.0
> Answers here are this project's source of truth.
> Re-generate or adopt a newer template only as a deliberate decision (`tpl update`).

---

## Phases (objective, size, exit criteria)

| Phase | Objective | Exit criteria |
|-------|-----------|---------------|
| 0 | Governance, workspace setup, bootstrap foundation | pytest runs; doc set committed |
| 1 | Domain models + LearningHubSTEM seam | 100% domain/adapter coverage; zero-drift tests |
| 2 | Multi-provider pool + circuit breakers | failover works on simulated 429/503 |
| 3 | Cognitive engine + Socratic agents | simulated-student Newton's 2nd Law pass |
| 4 | Platform parity (session/workspace/memory/tools) | ≥90% JARVIS capabilities operational |
| 5 | Code & math sandbox | sandbox blocks harmful calls; kills infinite loops |
| 6 | Knowledge, research & PDF pipeline | page-exact citations on ingested papers |
| 7 | Next.js 15 canvas UI | streaming tokens render with KaTeX |
| 8 | WebRTC voice classroom | <700 ms voice roundtrip |
| 9 | Mastery tracking, production, CI/CD | CI green; automated deploy |

## Timebox classification

- **NOW:** Phases 0–9 per roadmap priority.
- **SEAM:** LHS adapter contract, voice provider seam, DB engine (SQLite→Postgres),
  distributed event bus (Redis/NATS).
- **LATER:** multi-node scale-out, mobile native, multi-tenancy, payments, curriculum
  standards (CBSE/GCSE/NGSS/IB).

## Dependencies

- Phase 1 depends on LearningHubSTEM export schema being stable.
- Phase 2 depends on provider catalogs (JARVIS patterns).
- Phase 6 depends on Phase 2 (research uses model pool) and Phase 5 (sandbox).
- Phase 9 depends on all prior phases.

## Explicitly deferred items & triggers to pull forward

- Mobile native (trigger: proven web demand).
- Multi-tenancy (trigger: explicit owner decision).
- Payments (trigger: owner activation).

## What healthy and done look like at the end of the current phase

Phase 0 healthy = governed, documented, verified repository; green local test scaffold;
all foundation modules answered and consistent.