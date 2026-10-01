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
