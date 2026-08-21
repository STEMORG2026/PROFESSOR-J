# ADR-002: Pattern-Level Inheritance from JARVIS; No Package Coupling

- **Status**: accepted
- **Date**: 2026-08-21
- **Version**: 0.1.0
- **Commit**: eff694e
- **Decider**: Sajan (Principal Architect)

## Context

PROFESSOR-J inherits JARVIS's proven capabilities (cognitive brain, multi-provider model
pool with circuit breakers, hybrid memory, tiered safety gates, tool sandbox,
session/workspace management, FastAPI + Next.js UI). The workspace governance
mandates: "Repositories are independent peers. No repository is the backend of, or
subordinate to, another. Integration is via explicit contracts or adapters, never
embedding."

We must define how JARVIS capabilities transfer to PROFESSOR-J without violating
workspace invariants.

## Decision

All JARVIS capability transfer to PROFESSOR-J is **pattern-level only**:

1. **No package imports** — PROFESSOR-J never imports from `JARVIS/` at the Python
   package level. No `from jarvis.app...` or `sys.path` manipulation.

2. **Ported code is adapted** — JARVIS patterns are re-implemented in PROFESSOR-J's
   own package structure (`app/brain/`, `app/models/`, `app/memory/`, etc.) under
   PROFESSOR-J's governance.

3. **Every port is recorded** — Each capability ported from JARVIS gets an ADR
   documenting:
   - What pattern was ported
   - What was changed/adapted
   - Why deviations were made
   - Link to JARVIS source (commit/file)

4. **Contracts over coupling** — Integration with JARVIS (if ever needed) is via
   explicit versioned contracts/adapters, same as LearningHubSTEM.

5. **Governance applies** — Ported code follows PROFESSOR-J's `CONSTITUTION.md`,
   `RULES.md`, `STANDARDS.md`, not JARVIS's conventions.

## Consequences

### Positive

- Full compliance with workspace Level-1 invariants
- PROFESSOR-J owns its codebase completely — no hidden dependencies
- Clear audit trail of every architectural decision
- Freedom to diverge from JARVIS patterns when needed

### Negative

- More upfront work to re-implement rather than import
- Risk of subtle behavioral differences from JARVIS
- Must maintain parity checklist manually (see `IMPLEMENTATION-PLAN.md` §4)

### Neutral

- JARVIS continues evolving independently
- Pattern-level traceability via ADRs replaces git history traceability

## Alternatives

### Alternative 1: Git submodule or subtree

- Pros: Preserves exact code
- Cons: Violates "no embedding" invariant; creates deployment coupling

### Alternative 2: Shared library package

- Pros: DRY principle
- Cons: Creates package-level coupling; shared ownership ambiguity

## Related

- ADR-001: Successor decision
- ADR-003: Layered architecture + LangGraph
- `docs/GOVERNANCE.md` §4 (Successor relationship)
- `IMPLEMENTATION-PLAN.md` §4 (Successor Parity Check)
