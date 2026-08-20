# Agent Guide

> Companion: `agents` v0.1.0 from ProjectTemplates 0.1.0
> Answers here are this project's source of truth.
> Re-generate or adopt a newer template only as a deliberate decision (`tpl update`).

---

**Documents to read first, in order.**

1. `AGENTS.md`
2. `docs/GOVERNANCE.md`
3. `PRD.md`
4. `ARCHITECTURE-ESSENTIALS.md`
5. `ARCHITECTURE.md`
6. `IMPLEMENTATION-PLAN.md`
7. `docs/CONSTITUTION.md`, `docs/RULES.md`, `docs/STANDARDS.md`, `docs/PRINCIPLES.md`,
   `docs/WORKING-PROCEDURE.md`

**Commands for verification and how to run them.**

```bash
.venv/bin/python -m pytest tests/   # Python test suite
.venv/bin/mypy app/                 # strict typecheck
cd frontend && pnpm typecheck && pnpm lint
```

**Conventions that must not be violated, and where each is defined.**

- Domain purity, layering, sandbox-only execution — `docs/CONSTITUTION.md` §2.
- No package-level coupling to JARVIS/LearningHubSTEM — `docs/GOVERNANCE.md` §4,
  `ARCHITECTURE.md` §5.
- `@safety_gate` on every tool; HITL for destructive — `docs/ARCHITECTURE-ESSENTIALS.md` §4.
- Conventional Commits, strict typing, coverage floors — `docs/STANDARDS.md`.

**What not to do without permission.**

- Do not commit without running verification.
- Do not deploy, change public API contracts, or rename public things without the owner.
- Do not edit canonical LearningHubSTEM files (consume via adapter only).
- Do not create secrets or commit `.env`.

**How to leave a trail.**

- New architectural decision → ADR first (`docs/adr/`, MADR).
- Behavior changes → update relevant docs + changelog entry (`docs/600-changelog.md`).
- Commits reference the ADR/changelog where relevant.

**Derived artifacts are regenerable; answers in `docs/` are the source of truth.**
Anything generated (exports, indexes, caches, coverage) is disposable and rebuilt from
canonical content; the answered modules in `docs/` govern.