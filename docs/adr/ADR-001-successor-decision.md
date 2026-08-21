# ADR-001: Adopt PROFESSOR-J as General-Purpose AI OS Inheriting JARVIS Patterns

- **Status**: accepted
- **Date**: 2026-08-21
- **Version**: 0.1.0
- **Commit**: eff694e
- **Decider**: Sajan (Principal Architect)

## Context

JARVIS (v3.0.1) is a mature personal AI platform with 100+ tests, multi-provider LLM
routing with circuit breakers, hybrid memory (ChromaDB + BM25), tiered safety gates,
tool sandbox, session/workspace management, and FastAPI + Next.js UI. However, the name
"JARVIS" has copyright exposure (Marvel/Disney trademark), and its scope was personal
utility rather than a general-purpose platform.

We need a successor that:
1. Inherits all JARVIS capabilities under a new name
2. Generalizes beyond personal utility to a platform whose primary domains are
   tutoring, research, and general assistance
3. Is not bound to LearningHubSTEM but consumes it as one specialized knowledge source
4. Maintains pattern-level inheritance only (no package-level coupling)

## Decision

We adopt **PROFESSOR-J** as a general-purpose autonomous AI platform (AI OS) that
inherits JARVIS's proven architectural foundations under a new name and generalizes them.

Key positioning:
- **Not a JARVIS fork** — pattern-level inheritance only, recorded in ADRs
- **Not bound to LearningHubSTEM** — consumes via consumer adapter with provenance
- **General by default, specialized on demand** — tutoring/research are primary domains
- **Independent peer repository** — workspace Level-1 invariants apply

Branding: "PROFESSOR-J" leads; JARVIS relationship is internal history noted in governance/ADRs.

## Consequences

### Positive

- Clean copyright position with new name
- Architectural freedom to generalize beyond JARVIS's original scope
- Clear boundaries with LearningHubSTEM (consumer, not dependent)
- Governance framework established from day one

### Negative

- Must re-implement JARVIS capabilities rather than importing
- Brand recognition starts from zero
- Documentation overhead to maintain pattern-level traceability

### Neutral

- JARVIS remains an independent, maintained peer
- Pattern ports require ADR documentation (ADR-002)

## Alternatives

### Alternative 1: Fork JARVIS directly

- Pros: Faster initial implementation
- Cons: Copyright risk; package-level coupling violates workspace invariants; harder to generalize

### Alternative 2: Rename JARVIS in-place

- Pros: Preserves git history
- Cons: Same copyright issue; doesn't address scope generalization

## Related

- ADR-002: Pattern-level inheritance from JARVIS
- ADR-003: Clean layered architecture + LangGraph orchestration
- `docs/GOVERNANCE.md` §4 (Successor relationship)
- `PRD.md` §1 (Executive Summary)
