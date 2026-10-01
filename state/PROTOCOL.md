# PROTOCOL — MACP v2 (amended)

> **This is the authoritative operating protocol for this repository.** It supersedes the v1 text
> delivered in chat, which no agent can read. If you are an agent starting work here: read this,
> then `DASHBOARD.md`, then `REGISTRY.md`.
>
> **Version:** v2 · **Amended:** 2026-10-01 · **Amended by:** A7F3
> **Supersedes:** MACP v1 (verbatim, chat-only)

## Why v2 exists

v1 specified **actions** without **verifications**. That is an honour system, and it rots
deterministically. Every amendment below closes one feedback loop. The unifying principle:

> **Every assertion needs a verifier. Every state needs a transition. Every file needs an owner.**

| Amendment | Loop closed | Status |
|---|---|---|
| P1 — Shutdown Step 0 | finalize claim ↔ actually stopping | ADOPTED |
| P2 — Terminal verification loop | shutdown summary ↔ repo reality | ADOPTED |
| P3 — Re-open transition | COMPLETED status ↔ continued work | ADOPTED |
| P4 — State-file ownership table | event occurrence ↔ file update | ADOPTED |
| P5 — Reproducible records (principle) | written claim ↔ reproducibility | ADOPTED |
| P6 — Record verification in Section 3 | session file ↔ git truth | ADOPTED |
| P7 — Machine-checked drift | (automation) | **DEFERRED** — see §7 |

---

## P1 — Shutdown Step 0: STOP WORKING

Before any shutdown step: **stop producing work.** Not "wrap up" — stop.

If any new finding or change appears during shutdown, **abort the shutdown, return to Section 2,
fix it, and restart shutdown from Step 0.** Do not patch the summary to match. A "finalized"
record is a lie if work continues after it.

**Scope boundary** (a typo in your own summary is not a reason to restart):

- **ABORTS shutdown:** any code change, config change, or state-file change other than the session
  file being finalized; any new commit touching repo content; any new discovery that changes a claim.
- **DOES NOT abort:** fixing prose/formatting in the shutdown summary itself.

**Restart cap: 3 per session.** A fourth abort means the session is genuinely unstable — halt, set
outcome `PARTIAL`, and record `[NEEDS HUMAN]` in `BLOCKERS.md`.

**Completion discipline.** Declare completion only when every plan item is checked AND Section 3
validation passes. **User satisfaction is not a completion signal.** "Are you done?" is not
evidence; a green verification loop is.

**Mid-shutdown abort is NOT a re-open** (see P3). Re-open applies only after a shutdown fully
completed and `REGISTRY.md` was set to `COMPLETED`.

---

## P2 — Terminal verification loop (after shutdown, before declaring done)

After finalizing the session file, close the loop by verifying **the record against reality**.
Iterate until it converges. Nothing new may be *built* in this loop — that would falsify the thing
being verified.

**Classify every discrepancy — the fix differs:**

| Class | Meaning | Action |
|---|---|---|
| **Record error** | The record is wrong; reality is fine | Fix the record, re-verify |
| **Reality error** | The work is genuinely broken/incomplete | Fix reality → **this re-enters work mode → P1 aborts shutdown** |

**Checks that must actually be run (not eyeballed):**

1. `git log <base>..HEAD --oneline` — every commit appears in the session file's commit list.
2. `git status --porcelain` — clean; no orphan or forgotten artifacts.
3. `REGISTRY.md` "Active Agents" matches the session file header **exactly** (id, branch, status).
4. `DASHBOARD.md` alert/blocker rows match `BLOCKERS.md`.
5. Re-read the session summary cold: **every claim must be checkable** by a command or a file.

**Convergence:** each iteration strictly reduces discrepancies, so it terminates. **Cap: 3.**
If it does not converge, the session outcome is **`PARTIAL` or `FAILED`** — *not* `COMPLETED`,
regardless of what code shipped — and the divergence goes in `BLOCKERS.md`.

---

## P3 — Re-open transition (COMPLETED → ACTIVE)

If work continues after a shutdown completed, the status must **not** simply drift. Perform an
explicit transition:

1. Append to the session file: `## Re-opened: <UTC timestamp>` with a **structured** reason:
   - **Trigger:** user request | self-review | cold-read finding | new discovery
   - **Why not a new session:** <reason>
   - **Delta from the completed state:** <what changed>
2. Set `REGISTRY.md` status back to `IN-PROGRESS`.
3. **Git divergence check (mandatory):** `git fetch` and compare against the commit list in the last
   shutdown. If the branch moved or was merged, reconcile before proceeding.
4. Re-execute **the full shutdown** afterwards.

**Re-open vs new session:**

- **Re-open** when continuing the *same objective*, *same calendar day*, and no other agent worked in between.
- **New session** when the objective changed, the day changed, or another agent's session interleaves.

---

## P4 — State-file ownership table

**An event is anything that would make an existing claim in a state file false or incomplete.**

When an event occurs, **every** triggered file must be updated **in the same session**. A partial
update is a failure, not a partial success.

| Event | Files that MUST be updated |
|---|---|
| Structure changes (modules, layers, entry points, topology) | `ARCHITECTURE.md`, session |
| A hard-to-reverse choice is made | `DECISIONS.md` (ADR), session |
| Debt introduced or discovered | `DEBT.md`, session |
| Work blocked / needs human | `BLOCKERS.md`, session |
| Dependency added, removed, upgraded, or found undeclared | `DEBT.md`, session (+ `ARCHITECTURE.md` if it changes the stack) |
| CI/CD or workflow config changed | `ARCHITECTURE.md`, session |
| Environment variable added/removed | `ARCHITECTURE.md`, session |
| Public API / contract changed | `ARCHITECTURE.md`, session (+ `DECISIONS.md` if breaking) |
| Security-relevant finding | `DECISIONS.md` or `DEBT.md`, `BLOCKERS.md` if unresolved, session |
| Test suite restructured or baseline changed | `DEBT.md`, session |
| Session starts / ends / re-opens | `REGISTRY.md`, `INDEX.md`, session |

**Meta-rule: this table is incomplete by design.** If an event occurs that no row covers, add a row
as part of shutdown. The table grows by use, not by prediction.

---

## P5 — Reproducible records (principle, not ban)

> **Principle: every claim in a record is either (a) a durable historical fact that cannot change,
> or (b) a current-state claim paired with the command and timestamp that reproduce it.
> Unverifiable assertions rot.**

There is **no ban on concrete numbers** — a ban produces vague, protocol-compliant, informationally
dead prose. What matters is the *form*:

| Form | Verdict | Example |
|---|---|---|
| **Delta / historical marker** | ✅ allowed | "+30 tests added this session"; "at session start: 882 passing" |
| **Action timestamp** | ✅ allowed | "ADR-001 written at 12:20Z" |
| **State timestamp** | ⚠️ only with verification context | "DASHBOARD current as of `164d631`, verified via `git log -1`" |
| **Current-state claim, unpaired** | ❌ | "we have 1130 passing tests"; "7 commits ahead" |

Rule of thumb: **if a future reader cannot re-run something to check it, rewrite it.**

---

## P6 — Record verification in Section 3 (cheap, high value)

Add to the Section 3 checklist:

- [ ] Commit list in the session file is complete (`git log <base>..HEAD`)
- [ ] Statuses are current (no stale `IN-PROGRESS`)
- [ ] No checked-off TODOs for work that is actually unfinished
- [ ] Session header matches `REGISTRY.md`

**Session file header schema — MANDATORY.** Every session file begins with:

```
# Session <YYYYMMDD-HHMM>-<AGENT-ID> — <title>
- **Agent:**      <id> (<model/type>)
- **Branch:**     <branch> @ <short-sha>
- **Base commit:**<short-sha at session start>
- **Started:**    <UTC>
- **Status:**     IN-PROGRESS | COMPLETED | PARTIAL | BLOCKED | PIVOTED
```

These fields must match `REGISTRY.md`. Without the schema, "matches REGISTRY" is unenforceable.

*(The strongest form would require a cold re-read after a context break. That is not reliably
enforceable; this checklist is the honest floor.)*

---

## P7 — Machine-checked drift: DEFERRED

Not rejected. **Deferred deliberately.**

Tooling encodes assumptions about the protocol, and the protocol just changed materially. Build the
checker after P1–P6 have run for a non-trivial period, so it encodes **observed residual failures**
rather than guesses. When built:

- It is a **completeness** checker ("were the required files touched?"), not a correctness checker —
  content correctness is not decidable mechanically.
- Wire it as a **warning** pre-commit and a **blocking** CI check on merge to `main`. A blocking
  pre-commit hook trains `--no-verify` and minimal-record gaming, which is worse than no hook.

---

## Backlog — failure modes v2 does NOT yet address

Recorded honestly; each is a v3 candidate.

1. **Context-window pressure causes documentation collapse.** Record quality degrades first when
   context runs short, because it *feels* optional. No rule covers "stop and hand off cleanly."
2. **User-induced protocol violation.** "Just do X quickly, skip the protocol" has no defined
   response. Silence means agents comply silently — the worst option. Suggested default: comply only
   if the action is reversible and log `[PROTOCOL-SKIP] <reason>` in the session file.
3. **Protocol version drift mid-session.** If this file changes while you work, you are operating
   under two protocols. Rule: record the protocol version you started with, and re-read on change.
4. **The boring-update skip.** Trivial sessions get skipped as disproportionate, then the habit
   carries into substantial work. Needs a **minimum viable session record** — one line, not nothing.
