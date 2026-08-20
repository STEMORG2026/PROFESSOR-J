# Research Question

> Companion: `research-question` v0.1.0 from ProjectTemplates 0.1.0
> Answers here are this project's source of truth.
> Re-generate or adopt a newer template only as a deliberate decision (`tpl update`).

---

**The research question(s), in falsifiable form where possible.**

1. Can an autonomous AI platform grounded in a canonical knowledge base (LearningHubSTEM)
   reduce ungrounded STEM claims to **0%** for foundational queries (measurable: citation
   provenance on every factual claim)?
2. Can Socratic scaffolding (progressive hints, misconception diagnosis) achieve **≥ 85%**
   independent problem resolution versus direct-answer baselines?
3. Can a multi-provider model pool with 3-state circuit breakers maintain **99.9%**
   session uptime across simulated 429/503 provider failures?
4. Can page-exact citation provenance for ingested PDFs be maintained at scale
   (measurable: citation precision/recall on a test corpus)?

**Hypothesis.** Grounded context + pedagogical intent + resilient routing yields measurably
lower hallucination, higher learner independence, and higher availability than
single-provider, ungrounded, answer-first systems.

**Scope.** Single-tenant personal platform; STEM-first grounding; education + research +
general assistance domains. Unit of analysis: tutoring/research sessions.

**Definitions of central concepts.** Grounded (claim cites canonical entity ID); Socratic
(progressive scaffolding, not answer dumps); circuit breaker (CLOSED/OPEN/HALF_OPEN
provider health state); citation provenance (page-exact source for a claim).

**Why this question, and for whom the answer matters.** It tests whether a
general-purpose AI platform can be both broad and trustworthy — mattering to learners,
researchers, and the successor-vision of JARVIS.