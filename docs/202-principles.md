# Principles

> Companion: `principles` v0.1.0 from ProjectTemplates 0.1.0
> Answers here are this project's source of truth.
> Re-generate or adopt a newer template only as a deliberate decision (`tpl update`).

---

**Principles the project will not trade away, and why.**

1. **Provenance over generative** — a confident-sounding claim without source provenance
   is worse than an honest "no verified source". Trust is the product.
2. **Teach, don't just answer** — pedagogy is the differentiator; answer-first defeats it.
3. **Safety is a feature** — destructive operations always have a human checkpoint.
4. **Resilience by design** — no single provider/store/path is a single point of failure.
5. **General by default, specialized on demand** — a general platform that adds domains,
   never a single-purpose tool.
6. **Independence and integration by contract** — never embed or couple to another repo.
7. **Small verified increments** — tested increments beat speculative architecture.
8. **Leave a trail** — ADRs and changelog make every decision reconstructable.
9. **AI proposes, human decides** — nothing AI-produced is canonical without review.
10. **Keep status honest** — distinguish existing/planned/possible.

**Where priorities collide, what wins?**

- Grounded vs helpful → grounded wins for factual claims.
- Speed vs safety → safety wins.
- Specialization vs generality → generality is the floor.
- Autonomy vs control → autonomy up to the safety tier; humans keep destructive decisions.

**Principles inherited from the ecosystem.**

The workspace principles (`/home/sajan/Projects/docs/PRINCIPLES.md`) all apply and are
never contradicted. The full project-level stance is in `docs/PRINCIPLES.md`.

**How a principle violation should be reported and handled.**

Reported (issue/PR comment) → triaged → corrected, or turned into a recorded ADR that
documents the deliberate deviation.
