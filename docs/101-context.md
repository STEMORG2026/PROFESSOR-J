# Context

> Companion: `context` v0.1.0 from ProjectTemplates 0.1.0
> Answers here are this project's source of truth.
> Re-generate or adopt a newer template only as a deliberate decision (`tpl update`).

---

**What is going on around this project that it must fit into?**

This project lives in the STEM ecosystem workspace (`/home/sajan/Projects`), where
repositories are independent peers: `LearningHubSTEM` (canonical STEM knowledge
foundation), `STEM-TUITION` (flagship learning product), `JARVIS` (personal AI platform),
and others. PROFESSOR-J is a consumer of LearningHubSTEM's canonical knowledge exports and
the successor to JARVIS. It must respect workspace governance (Level-1 invariants) and
integrate only through explicit contracts/adapters.

**Why now? What changed to make this worth doing?**

JARVIS proved a capable personal AI platform (105+ tests, multi-provider routing, hybrid
memory, safety gates) but the name has copyright exposure, and its scope was personal
utility. PROFESSOR-J takes that proven engine, renames it, and generalizes it into a
platform whose primary domains are tutoring, research, and general assistance — grounded
in LearningHubSTEM where canonical entities exist.

**What already exists that this project inherits, builds on, or depends on?**

- **JARVIS** — capabilities/patterns (cognitive brain, guardrails, model pool, memory,
  session/workspace, tool sandbox, FastAPI + Next.js UI). Pattern-level inheritance only.
- **LearningHubSTEM** — canonical knowledge exports (`exports/knowledge.json`) consumed
  through an adapter.
- **ProjectTemplates** — the Project Operating System that generated this document set.

**What must not change while this project runs?**

Workspace Level-1 invariants (independent peers, no embedding, human-review-of-AI-output,
derived-not-canonical, status honesty) and the repository's own governance non-negotiables
(domain purity, sandboxed execution, safety tiers, failover resilience).

**Who initiated it, and with what expectation?**

Sajan. Expectation: a general-purpose autonomous AI platform (JARVIS 2.0) that is better
than its predecessor, education-capable but not education-limited.
