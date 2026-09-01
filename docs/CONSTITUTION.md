# CONSTITUTION — PROFESSOR-J

**Version:** 0.1.0 (Constitution adoption draft)
**Status:** Draft for adoption
**Owner:** Sajan (Principal Architect)
**Applies To:** All packages, apps, and the repository root
**Related:** `docs/GOVERNANCE.md`, `docs/RULES.md`, `docs/STANDARDS.md`,
`docs/PRINCIPLES.md`, `docs/WORKING-PROCEDURE.md`, `ARCHITECTURE.md`

**Document Type:** Governing Development Specification

---

# 0. PURPOSE

This document is the **development constitution**. It defines how PROFESSOR-J is to be
designed, implemented, documented, tested, debugged, governed, and evolved.

It exists so that the human developer, current AI coding agents, future AI coding agents,
future human developers, and future maintainers can understand not only **what the system
does**, but also:

- why it is structured this way,
- where responsibilities belong,
- what decisions have already been made,
- what may be changed freely,
- what requires approval,
- what is intentionally deferred,
- how to inspect the system,
- how to debug it,
- and how to extend it without creating architectural drift.

---

# 1. WHAT PROFESSOR-J IS

PROFESSOR-J is the **next-generation successor to JARVIS** — an autonomous, general-purpose
AI platform. It is an **Autonomous AI Professor, Research Companion, and Personal AI
Engine** with the full capability surface of its predecessor and a broader mission.

It is **not** a single product: it is a platform whose primary domains include tutoring,
research, coding, and everyday personal assistance — grounded in verified knowledge when
available, and capable of operating generally when not.

# 2. NON-NEGOTIABLES

These constraints may not be traded away without a recorded ADR that the human owner
accepts:

1. **Provenance over generation.** Factual claims that map to a canonical source (e.g.
   LearningHubSTEM) must cite that source **and surface its review status** (`status`,
   `provenance`). Ungrounded content is clearly labeled as ungrounded.
2. **Domain purity.** `app/domain/` contains pure Python dataclasses only — zero imports
   from adapters, brain, db, or external frameworks.
3. **Layered dependency direction.** Presentation → adapters → bootstrap → brain → domain.
   No layer may import upward.
4. **Failover resilience.** No single LLM provider outage may take down a session.
5. **Sandboxed execution.** Code execution never runs in the host web-server process; it
   runs in an isolated, resource-capped sandbox behind `@safety_gate`.
6. **Safety by default.** Every tool has an explicit safety tier; destructive operations
   require human-in-the-loop approval.
7. **Zero secrets.** No secrets in code or docs; environment variables only.
8. **Derived is never the source of truth.** Exports, indexes, caches, and generated
   artifacts are regenerable and disposable.
9. **Humans decide.** AI agents propose and draft; the human owner decides. Nothing
   AI-produced becomes authoritative without review.

# 3. HOW THE PROJECT IS GOVERNED

- Authority precedence: workspace L1 → PROFESSOR-J L2 → architecture → implementation
  (see `docs/GOVERNANCE.md`).
- Decisions are recorded in `docs/adr/` (see `docs/301-decisions.md`).
- Enforceable rules live in `docs/RULES.md`.
- Standards for coding, docs, and working live in `docs/STANDARDS.md`.
- The values the project commits to live in `docs/PRINCIPLES.md`.

# 4. SCOPE DISCIPLINE

All work is classified NOW / SEAM / LATER / OUT OF SCOPE (see `docs/GOVERNANCE.md` §3).
The roadmap and its phase gates are in `docs/400-roadmap.md` and `IMPLEMENTATION-PLAN.md`.

# 5. AMENDMENT

This constitution is amended only by a recorded ADR accepted by the human owner. Agents
may propose amendments; they may not adopt them unilaterally.
