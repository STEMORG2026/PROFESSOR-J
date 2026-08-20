# Goals & Non-Goals

> Companion: `goals` v0.1.0 from ProjectTemplates 0.1.0
> Answers here are this project's source of truth.
> Re-generate or adopt a newer template only as a deliberate decision (`tpl update`).

---

## Objectives (what must be true when the project succeeds)

1. **JARVIS parity + generalization:** ≥ 90% of JARVIS capabilities operational in
   PROFESSOR-J by end of Phase 4, with the platform capable of general assistance
   (chat, files, workspace, code) beyond education.
2. **Grounded tutoring:** 0% ungrounded formula citations in foundational STEM queries;
   every factual claim cites a canonical entity ID.
3. **Effective pedagogy:** ≥ 85% of tutoring sessions end with the learner independently
   solving the target problem.
4. **Research capability:** ingested PDFs are queryable with page-exact citations.
5. **Resilience:** 99.9% uptime across the multi-provider pool with sub-200ms failover.
6. **Governed, documented, tested:** full governance suite, ≥ 95% domain/brain coverage,
   ≥ 85% adapter coverage, all decisions in ADRs.

## Success criteria (how each is verified)

- Parity: capability checklist against JARVIS in `docs/adr/`.
- Grounding: citation-audit tests over foundational query set.
- Pedagogy: simulated-student and user trials measuring independent resolution.
- Research: citation precision/recall on a test corpus.
- Resilience: fault-injection tests (429/503) with uptime telemetry.
- Governance/coverage: CI gates + coverage reports.

## Explicit non-goals

- Multi-tenancy / SaaS / payments.
- Mobile native apps.
- Guaranteed accuracy for arbitrary ungrounded topics (labeled ungrounded instead).
- Replacing human teachers.
- Coupling to JARVIS/LearningHubSTEM at the package level.

## Definition of done for the first complete milestone (Phase 0)

Governed, documented repository with verification scaffolding that runs and passes;
the full doc set (governance + foundation modules) committed and consistent.