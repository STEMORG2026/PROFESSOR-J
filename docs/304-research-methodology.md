# Methodology

> Companion: `research-methodology` v0.1.0 from ProjectTemplates 0.1.0
> Answers here are this project's source of truth.
> Re-generate or adopt a newer template only as a deliberate decision (`tpl update`).

---

**Method choice and the reasoning vs alternatives.**

Mixed empirical approach: (a) engineering validation via deterministic tests and
fault-injection (circuit breakers, sandbox, grounding audits), and (b) quasi-experimental
learner trials for pedagogical effectiveness (Socratic vs direct-answer). Chosen because
the product claims are both mechanical (reliability) and behavioral (learning).

**Study design and controls.**

- Reliability: synthetic fault-injection (429/503, timeouts, sandbox escape attempts)
  against a control of single-provider/no-breaker.
- Pedagogy: A/B — Socratic-scaffolding group vs direct-answer group on matched diagnostic
  problems; measure independent resolution rate.
- Grounding: citation audit over a fixed foundational query set; assert 0% ungrounded
  formula citations.

**Data: sources, collection, quantities, variables.**

Sources: test harness logs, telemetry bus, learner trial outcomes. Variables: resolution
rate, citation coverage, failover latency, uptime. Collection is automated via the event
bus and CI runs.

**Analysis plan.** Compare resolution rates and reliability metrics against targets
(≥85% resolution, 0% ungrounded, 99.9% uptime, sub-200ms failover). Report as evidence in
`docs/adr/` and changelog.

**Anticipated limitations.** Small sample sizes in early trials; results are indicative,
not statistically powered; conclusions are kept within bounds.

**Ethical review & informed consent.** Learner trials are low-risk tutoring interactions;
participants are informed that sessions may be used (anonymized) for evaluation. No
sensitive data collected; no deception.