# WORKING-PROCEDURE — PROFESSOR-J

**Status:** How work gets done inside this repository.
**Related:** `AGENTS.md` (routing), `docs/GOVERNANCE.md` (authority),
`docs/RULES.md` (rules), `docs/STANDARDS.md` (standards).

---

## 1. Starting work

1. Read, in order: `AGENTS.md`, `docs/GOVERNANCE.md`, `PRD.md`,
   `ARCHITECTURE-ESSENTIALS.md`, `ARCHITECTURE.md`, `IMPLEMENTATION-PLAN.md`.
2. Read the relevant `docs/` foundation module(s) for the area you are touching.
3. Classify the work **NOW / SEAM / LATER / OUT OF SCOPE**.
4. State a short plan before modifying files.

## 2. During work

- Write tests alongside implementation (TDD encouraged).
- Follow `docs/STANDARDS.md` (coding, docs).
- Respect `docs/CONSTITUTION.md` non-negotiables and `docs/RULES.md`.
- Do not silently expand scope; ask the human when in doubt.
- New architectural decisions → write the ADR first (`docs/adr/`, MADR format).

## 3. Finishing work

1. Run the verification commands (`AGENTS.md` §5): pytest, mypy, frontend typecheck/lint.
2. Update the relevant docs if behavior changed.
3. Review your diff for secrets, scope creep, and layering violations.
4. Commit with a Conventional Commit message.
5. If a version bump is required, update `docs/600-changelog.md` in the same change.

## 4. Verification commands

```bash
.venv/bin/python -m pytest tests/     # complete Python test suite
.venv/bin/mypy app/                   # strict typecheck
cd frontend && pnpm typecheck && pnpm lint
```

## 5. Escalation

A conflict that cannot be resolved by the authority hierarchy is flagged and escalated to
the human (issue labeled `escalation`). The human's decision is recorded in `docs/adr/`.

## 6. Recording a decision (ADR)

- File: `docs/adr/ADR-XXX-<slug>.md`
- Format (MADR): Status · Date · Context · Decision · Consequences · Alternatives.
- Trigger: any significant architectural or product decision, or a deliberate deviation
  from this governance.