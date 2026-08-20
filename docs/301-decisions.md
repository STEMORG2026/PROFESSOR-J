# Decision Records

> Companion: `decisions` v0.1.0 from ProjectTemplates 0.1.0
> Answers here are this project's source of truth.
> Re-generate or adopt a newer template only as a deliberate decision (`tpl update`).

---

**ADR format.** MADR: Status · Date · Context · Decision · Consequences · Alternatives.

**Status ladder.** proposed → accepted → superseded → rejected, each transition dated and
attributed to a decider (default: Sajan).

**Where decision records live.** `docs/adr/ADR-XXX-<slug>.md`. Start numbering at
`ADR-001`.

**Planned initial records** (write with the work that implements them):

- `ADR-001` — Adopt PROFESSOR-J as successor to JARVIS (rename, generalization, platform
  positioning).
- `ADR-002` — Pattern-level inheritance from JARVIS; no package coupling.
- `ADR-003` — Clean layered architecture + multi-agent cognitive engine.
- `ADR-004` — LearningHubSTEM consumer adapter contract (zero-drift, versioned export).
- `ADR-005` — `@safety_gate` tiered policy with HITL.
- `ADR-006` — Multi-provider router with 3-state circuit breakers.
- `ADR-007` — Hybrid memory (ChromaDB + BM25) behind `MemoryService`.

**What triggers a new record.** Any new architectural decision, a deliberate deviation
from governance, a change to a stable interface, or a significant product-scope change.
Inline remarks are not a substitute.
