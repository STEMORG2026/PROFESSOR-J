# DECISIONS — Architecture Decision Records

> Record choices that are hard to reverse or that a future agent might otherwise undo.
> Format: context → decision → consequences → alternatives rejected.

---

## ADR-001: `state/` is exempt from per-file documentation classification

**Date:** 2026-10-01 · **Status:** Accepted · **Agent:** A7F3

**Context.** Two governance systems now meet. MACP requires a committed `state/` directory whose
contents change on **every agent session** (`sessions/`, `plans/`, `INDEX.md`). This repository's
documentation governance requires that `docs.manifest.yaml` classify **every** markdown file
exactly once, and the gate **fails** on an unclassified file. Enumerating each session file would
break the gate on every future session, which would train agents to bypass the gate — the exact
failure mode the gate exists to prevent.

**Decision.** Add first-class support for a **reasoned subtree exemption** in
`scripts/docs/manifest_validate.py`, and exempt `state/` as a unit with a written justification.
The exemption is explicit, auditable, and cannot be granted silently.

**Consequences.**
- `state/**/*.md` is excluded from classification *and* from co-change *and* from the doc universe.
- The exempted subtree is printed by the validator on every run, so the exemption stays visible.
- `state/` files are not held to doc standards (freshness headers, single H1, link checks).

**Alternatives rejected.**
1. *Add `state/` to `.git/info/exclude`* — defeats MACP; state must be committed and shared.
2. *One manifest entry per file* — breaks on every new session file.
3. *Mark each file `standalone, reviewed <date>`* — same churn problem; also dishonest, because
   these files do not get reviewed.
4. *Put `state/` outside the repo* — defeats cross-agent coordination entirely.

---

## ADR-002: The GitHub ruleset stays in `evaluate` until the mirror is green

**Date:** 2026-10-01 · **Status:** Accepted · **Agent:** A7F3

**Context.** The ruleset `main` requires two status checks. `Documentation gate` passes;
`Local gate` fails on a clean runner. `bypass_actors` is empty and
`current_user_can_bypass` is `never`, so a wrongly-required check cannot be overridden — it
deadlocks every PR with no escape.

**Decision.** Keep `enforcement: evaluate` (rules report but do not block) until the mirror passes
on a clean runner. Only then set `active`.

**Consequences.** Enforcement is advisory in the meantime. This is deliberate: a gate that blocks
everything is one people learn to bypass, and with no bypass actor the failure mode is total.

**Alternatives rejected.** `active` now (deadlocks the repo); adding a bypass actor (defeats the
purpose of the ruleset).

---

## ADR-003: Adopt MACP v2 (P1–P6), defer P7

**Date:** 2026-10-01 · **Status:** Accepted · **Agent:** A7F3

**Context.** MACP v1 specified actions without verifications. Reviewed adversarially as P1–P7;
the review found v1 rots deterministically because nothing closes the loop between a claim and the
reality it claims. Critically, v1 existed **only in a chat message**, so no future agent could read
it — making the protocol itself a lost-context artefact.

**Decision.**
- Adopt **P1** (stop-work barrier before shutdown, with a scope boundary and a 3-restart cap),
  **P2** (terminal verification loop, classifying record-errors vs reality-errors, capped at 3, and
  forbidding new work inside the loop), **P3** (explicit `COMPLETED → ACTIVE` re-open with a
  structured reason and a git-divergence check), **P4** (event→file ownership table, incomplete by
  design and extended by use), **P5** *as a principle rather than a ban* (deltas and action
  timestamps stay legal; unpaired current-state claims do not), **P6** (record verification in
  Section 3 + a mandatory session-file header schema).
- **Defer P7** (machine-checked drift) on its own argument: build the checker after P1–P6 have been
  exercised, so it encodes observed failures rather than guesses. When built it must be a
  *completeness* checker, a warning pre-commit, and a blocking CI check.
- Persist all of it at `state/PROTOCOL.md` so it survives the session.

**Consequences.**
- Shutdown becomes more expensive and more honest. Work that continues after finalization must be
  re-opened explicitly rather than silently.
- A non-converging verification loop marks the session `PARTIAL`/`FAILED` even if code shipped.
- `state/` now holds the governing protocol, so ADR-001's exemption is load-bearing, not cosmetic.

**Alternatives rejected.** Keeping the protocol in chat (proven to lose it); adopting P5 as a
blanket ban on numbers (produces vague but compliant prose — informationally dead); shipping P7 now
(encodes guesses; a blocking pre-commit trains `--no-verify`).

**Explicitly deferred to a v3 backlog** (recorded in `state/PROTOCOL.md`): context-window pressure
causing record collapse; user-induced protocol violation; protocol version drift mid-session;
the "boring update" skip.
