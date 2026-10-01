# Open Work and Resume Guide

> **Purpose.** Everything needed to continue this work without re-deriving it: what was built, how
> to verify it, what is genuinely unfinished, and the traps that will otherwise cost you a day.
> **Last updated:** 2026-09-30
> **Status**: the local gate passes 14/14. Two product defects are declared, not fixed.

---

## 0. Resume in sixty seconds

```bash
cd /home/sajan/Projects/PROFESSOR-J
bash scripts/setup_hooks.sh --check        # is the pre-push hook installed on THIS clone?
python3 scripts/ci_gate.py                 # the gate: 14 stages, ~8 min
python3 scripts/ci_gate.py --quick         # docs + governance only, ~5 s
python3 scripts/verify_repeat.py --runs 3 --control   # N consecutive passes, ~1 min
```

Read `docs/500-software-testing.md` for the testing and enforcement model, and
`scripts/declared_defects.py` for the two known-broken things. Those two files plus this one are the
whole picture.

**The single most important caveat in this document:** git cannot auto-install hooks, so a **fresh
clone is unprotected until someone runs `bash scripts/setup_hooks.sh`**. Enforcement is real, but it
is per-clone. See §5.1.

---

## 1. State at a glance

| Thing | State |
|---|---|
| Local gate (`scripts/ci_gate.py`) | **14/14 stages pass** |
| Pre-push hook | Installed on this clone; `--self-test` proves it can refuse |
| Repeat verification | **5/5 checks pass 3 consecutive runs**, positive control fires |
| Docs manifest | 67 docs classified exactly once (+10 exempt under `state/`), 58 code bindings resolve |
| Executable docs | 3 executed, 1 doctested, 12 compiled-only |
| Declared product defects | 9 failing tests, 5 tools without `@safety_gate` |
| Intermittent tests | 1 (`test_benchmark_2_farming_production`, ~75%); deselected from the gate, rate-measured nightly |
| CI (GitHub) | A **mirror**; a branch ruleset now requires its two jobs. Currently `enforcement: evaluate`, not yet blocking — see §4 |

Verification commands actually run, and their results, are in `docs/600-changelog.md`.

---

## 2. What is done

### 2.1 The enforcement chain

Enforcement had to move local because GitHub would not enforce it here: at the time the repository
was private on the free plan, so the branch-protection API returned `403`. Historically 30 of 30 CI
runs on `main` concluded `failure` while merges proceeded — a red pipeline was a notification, not a
barrier.

**This changed on 2026-10-01.** The repository is now public and organization-owned, and a ruleset
named `main` requires the gate mirror's two checks. It sits in `enforcement: evaluate` until
`Local gate` actually passes on a clean runner — see §4 and `state/DECISIONS.md` ADR-002.

| Artefact | Role |
|---|---|
| `scripts/ci_gate.py` | The gate. 14 stages, no bypass flag, every stage runs, missing tool = failure |
| `githooks/pre-push` | Runs the gate before any ref leaves the machine. `--no-verify` not honoured |
| `scripts/setup_hooks.sh` | Installs `core.hooksPath=githooks`; `--check` reports state |
| `scripts/verify_repeat.py` | Requires N **consecutive** passes, per-run logs, positive control |
| `scripts/ratchet.py` | Lint/format baselines: fail on new violations **and** on stale entries |
| `scripts/declared_defects.py` | The two known defects, by name, printed every run |
| `.github/workflows/gate-mirror.yml` | CI replaying the same entry point, plus an explicit docs job |

### 2.2 Documentation governance

Documentation is enforced, not advisory. Five checkers under `scripts/docs/`, all wired into the
gate. `docs.manifest.yaml` classifies every markdown file exactly once with `kind`, `staleness`,
`covers` and `owner`; the rules are documented in the manifest header and in
`docs/500-software-testing.md`.

Key mechanics a newcomer must know:

- **Most-specific-cover-wins.** A file matching both a broad binding (`app/`) and a narrow one
  (`app/main.py`) *blocks* on the narrow one and only *warns* on the broad one. Without this, any
  change anywhere in `app/` would demand an edit to `ARCHITECTURE.md` and the rule would be bypassed
  within a week.
- **`Docs-Not-Needed: <reason>` is the only escape**, and it must be an explicit commit trailer.
  Silence is never accepted as a reason.
- **A `snapshot` doc must never be edited in place.** It is superseded, not corrected. Binding live
  code to a snapshot produces a permanent, unsatisfiable co-change finding — this actually happened
  and was fixed by moving ownership to a live doc.
- **Co-change compares commits when pushed.** `--full` (worktree vs HEAD) passes *vacuously* on a
  clean tree, which is the normal state at push time. The hook passes `--docs-range <base>..<sha>`
  so the check examines the commits actually being published.

### 2.3 Repeat-run verification and declared defects

Three mechanisms share one rule — **an exemption without an expiry becomes a permanent blind spot**:
`scripts/ratchet.py`, `scripts/verify_repeat.py` known-defect handling, and `scripts/declared_defects.py` all fail when a
declared exemption stops reproducing.

---

## 3. What is left

In priority order. Each item states what to do, not just that something is wrong.

### 3.1 — Five tools execute without `@safety_gate` **(security, do this first)**

**Where:** `app/tools/`. **Evidence:** `python3 scripts/board/review.py` →
`FAIL safety_gate_coverage: 5 tools missing @safety_gate`, on the unmodified tree.

`AGENTS.md` §3.5 requires code execution to run through `app/tools/sandbox.py` behind
`@safety_gate(tier=SafetyTier.DESTRUCTIVE)` with explicit human-in-the-loop authorization. Five
tools bypass that. This is the highest-priority item on this list because it is a real security
boundary rather than a quality metric.

**Next action:** identify them with `scripts/board/review.py` (it prints the violation list), decide
per tool whether it genuinely executes code, and either decorate it or narrow the check with a
stated reason. Then delete the `DECLARED_BOARD_DEFECTS` entry in `scripts/declared_defects.py` — the
gate *fails* if you fix it and leave the declaration behind.

**Needs:** authorization to change `app/`.

### 3.2 — The repair benchmark is intermittent, and that is itself the finding

**Where:** `tests/unit/gamedev/test_v05_novel_benchmarks.py::test_benchmark_2_farming_production`
**Evidence:** failed **3 of 13** isolated runs, and **4 of 10** with `PYTHONHASHSEED=0` pinned.

The test drives the model-backed repair loop (`app/gamedev/`) and asserts the repair succeeds. It
usually does. Sometimes it does not, and the whole assertion arrives as `assert False is True`.

Diagnosis, recorded so nobody repeats it:

- **Not a timeout.** The failing run reported `exit_code=1, duration_ms=961` against the sandbox's
  10-second watchdog, so the subprocess was never killed.
- **Not hash ordering.** It still failed 4 of 10 with `PYTHONHASHSEED=0`, which rules out
  `set`-iteration order as the cause.
- **What it actually is.** The failing report carried `iterations: 1`: a proposal is applied, the
  test still fails, and the next iteration judges no further edit safe and stops. The probable cause
  is the fallback repair path being sensitive to `stdout[:1500]` truncation, whose cut point shifts
  with the random temp-directory name — but that is a hypothesis, not a measurement.

**What was done.** The test is marked `nondeterministic_repair` (registered in `pyproject.toml`) and
**deselected from the gate**, so the gate is deterministic. This is not concealment: a nightly job
runs it 20 times and publishes the success rate, failing only below a 50% floor. Excluding it is a
decision about *where* it is measured, not permission for it to fail.

**What is left.** The root cause is in `app/gamedev/`, which this change was not authorized to
touch. The honest fixes are to make the repair path deterministic with respect to stdout truncation,
or to inject a deterministic reasoner so the benchmark measures the *mechanism* rather than the
model's luck. Until then, **a single green run of this benchmark means nothing.**

### 3.3 — Coverage floors that are documented but unmet

| Scope | Documented | Measured | Enforced |
|---|---|---|---|
| `app.domain` | ≥ 95% | 100.0% | yes, gated |
| `app.brain` | ≥ 95% | 96.5% | yes, gated |
| `app.tools` | ≥ 95% | 83.3% | no — advisory |
| `app.adapters` | ≥ 85% | 67.5% | no — advisory |

An audit found **five** documented coverage standards and **one** gate. Two are now gated because
they already pass. The other two are measured and reported, and the docs state the gap explicitly,
because gating a scope 12–17 points below its documented floor makes the gate red for reasons
unrelated to the change being pushed — and a permanently-red gate is one people learn to bypass.

**Next action (needs a human decision):**

- **(A)** Ratify the floors and write ~90 statements of tests. Most rigorous; blocks `app.tools`.
- **(B)** Revise the floors to the measured baseline and ratchet upward with `scripts/ratchet.py`.
- **(C)** Exclude thin HTTP files (e.g. `app/adapters/api.py`) with a stated reason, then re-measure.

Whichever is chosen, `scripts/docs/check_standard_reality.py` will fail the gate if a documented
threshold has no enforcing gate — that is deliberate and should not be relaxed.

### 3.4 — `app/skills/builtin.py` is not formatted

`ruff format` rewrites **339 lines** of semantically-neutral code there. Two decisions were made
deliberately: it was reverted rather than smuggled into a tooling change, and the `format` ratchet
was built to hold it. The format baseline is otherwise **empty** (zero violations), so the ratchet
is genuinely tight.

**Next action:** reformat it in its own commit, then run `python3 scripts/ratchet.py format --update`
to record the (empty) baseline. Review that commit on its own — it will be large and boring, which
is exactly when a real change hides well.

**Residual lint debt:** `scripts/ratchet.py lint` currently baselines 5 files
(`app/routers/chat.py`, `app/routers/lh_integration.py`, `app/skills/builtin.py`,
`tests/unit/authority/test_build1_identity_gateway.py`, `tests/unit/authority/test_phase6_security.py`).
Removing them is straightforward but was out of scope here.

### 3.5 — CI and local run *different linters*

`.github/actions/setup-env/action.yml` pins `ruff==0.6.9`, `mypy==1.14.1`, `pre-commit==4.0.1`, while
`requirements.txt` declares `0.16.5`, `2.3.1`, `4.6.2`. The mirror will eventually disagree with the
gate for reasons that have nothing to do with the code — the worst kind of disagreement, because it
teaches people the mirror is noisy.

**Next action:** pick one source of truth for tool versions (the lockfile) and have the CI action
install from it rather than pinning separately.

### 3.6 — Layer 1 (fast, staged checks) is not wired to a commit hook

`scripts/docs/check_changed.py` supports a fast staged-only mode, but **no `githooks/pre-commit`
exists**. Today drift is caught at *push*, not at *commit*.

This is worth flagging loudly because it is precisely the failure this system was built to avoid:
the repository whose documentation governance this is modelled on documented a Layer 1 pre-commit
hook that **was never actually wired** — zero `repo: local` entries — so its guarantee was fictional
for as long as it existed.

**Next action:** add `githooks/pre-commit` running the cheap checks that suit a commit
(`scripts/docs/manifest_validate.py`, `scripts/docs/check_changed.py` in staged mode, `scripts/docs/check_docs.py`). Two cautions:

1. Keep it **fast** (< 2 s) or people will use `--no-verify` and the hook will train them to.
2. **See §5.2** — `core.hooksPath=githooks` disables the `.pre-commit-config.yaml` framework hooks.
   Any `githooks/pre-commit` must therefore either delegate to that framework or replace it
   knowingly.

### 3.7 — Most documented examples still only compile

Only **3 of 12** Python blocks in markdown are executed; the rest are `compile()`-checked. Compiling
never catches a bad import — proven, not theorised: two of the first three examples written for this
work imported `app.auth` and then `verify_password`, neither of which exists, and `compile()`
accepted both. Only executing them found it.

**Next action:** promote high-value blocks (those showing API usage, imports, or commands) to
`<!-- name: test_* -->` blocks. Each one must actually pass, so this is real work per block.

### 3.8 — Warning debt

`scripts/docs/check_docs.py` reports ~348 warnings and co-change ~5, none blocking. They are mostly staleness
warnings. Tightening rules from warn to error is the natural ratchet, and should be done
incrementally or the gate becomes red and ignored.

---

## 4. Why CI is a mirror, not the gate

```
$ gh api repos/Er-Sajan-PLG/PROFESSOR-J/branches/main/protection
403  Upgrade to GitHub Pro or make this repository public to enable this feature.
```

That was verified, not assumed — and the message names its own remedy, which was then taken. The
repository is now **public and organization-owned**, and the same call against the new location
returns `404 Branch not protected` rather than `403`: protection is *available and unset*, not
forbidden.

A ruleset named `main` now targets `~DEFAULT_BRANCH` and requires exactly two status checks —
`Local gate, replayed on a clean runner` and `Documentation gate (explicit, non-skippable)` — plus
deletion/force-push blocking, linear history, and **no bypass actors**.

**It is deliberately left at `enforcement: evaluate`, not `active`.** The required `Local gate`
check does not yet pass on a clean runner, and with `bypass_actors: []` a wrongly-required check
deadlocks every PR with no escape. Enforcement therefore still lives in `githooks/pre-push`.

**If CI ever fails where the local gate passed, that is a bug in the gate.** Add the missing stage to
`scripts/ci_gate.py` — do not start relying on CI to notice things. That rule is written down because
treating CI as the real gate is how this repository ended up with an unread red pipeline.

---

## 5. Landmines

### 5.1 A fresh clone is unprotected until you install the hook

Git has no mechanism to auto-install hooks from a repository. `git config core.hooksPath githooks`
lives in `.git/config`, which is not versioned. So on a fresh clone:

```bash
bash scripts/setup_hooks.sh          # required, once per clone
bash scripts/setup_hooks.sh --check  # verify
```

Until then the gate is advisory and the enforcement claim is false for that clone. **If you are
auditing whether enforcement is real, check this first.**

### 5.2 Installing the hook *disables* the `.pre-commit-config.yaml` framework

`core.hooksPath` redirects git's entire hook lookup to `githooks/`. Consequences:

- Anything previously installed by `pre-commit install` into `.git/hooks/` **will not run**.
- There is no `githooks/pre-commit`, so **nothing runs at commit time** today.

This is deliberate for `pre-push` (the gate replaces it, and does far more), but it is a real
interaction rather than a no-op. See item §3.6.

### 5.3 Never run `pre-commit run --all-files`

It is still listed in older instructions, and it **rewrites the tree** (measured at `42b2587`:
`ruff format --check` would reformat 6 files). The gate checks read-only precisely so a verification
run cannot dirty the working tree. Use `pre-commit run --files <paths>` for a specific change.

### 5.4 Docs checkers that read the git index will mislead you

`scripts/docs/check_docs.py` and `scripts/docs/check_standard_reality.py` default to reading the **git index**, which is right
for pre-commit (the index is what is about to be committed) and **wrong for the gate** (which runs
against the working tree). Without `--worktree`, an unstaged doc fix is invisible and the checker
reports the *old* text — which reads as "my fix did nothing". Both now take `--worktree`, and the
gate and `scripts/verify_repeat.py` pass it. This bug was found twice, in two different checkers.

### 5.5 The manifest universe includes *untracked* markdown

`tracked_markdown()` uses `git ls-files --cached --others --exclude-standard`, deliberately: with
plain `git ls-files`, a brand-new doc escapes classification at exactly the moment someone is
writing it. That is why `_audit/` is in `.git/info/exclude` — it keeps scratch material out of the
governed universe. **If you add a scratch markdown file somewhere git can see it, the gate will
fail until you classify it or exclude it.**

### 5.6 Coverage stages are judged on the JSON report, not pytest's exit code

This repository carries 9 known failing tests. `--cov-fail-under` therefore prints "Required test
coverage reached" *and* pytest exits 1, simultaneously. Keying the stage on the exit code would
report a coverage failure that is really a test failure — the same defect twice, with the coverage
number rendered unreadable. The stages read `totals.percent_covered` from `coverage.json` instead
(`--cov-report=json:coverage.json`). pytest-cov 7.1.0 has no `--cov-ignore-errors`.

### 5.7 `mypy app/` is not the enforcing type gate

`pre-commit` runs `mypy app/ tests/ scripts/`. The narrower `mypy app/` hides real errors in the
tooling — eight of them, when this was measured. Use the full invocation.

### 5.8 Known environment traps

- **`PROFESSOR_SQLITE_PATH` is inert.** A future isolation fixture must patch `db_path`
  (`app/bootstrap.py:103`) rather than the environment variable.
- **`tests/unit/voice/test_voice.py::test_piper_download_voice_downloads_both_files` performs a live
  network download.** It fails offline and is not hermetic when it succeeds. The fix is a local
  fixture, not deletion.
- **`scripts/docs/check_executable.py` imports the whole app to find doctests**, and that import has
  a visible side effect: it can quarantine a corrupt temp memory file. Exit code stays 0; the
  verifier's digest logic normalises the volatile temp path so this does not read as
  nondeterminism.

---

## 6. Decisions needed from a human

1. **Coverage standard** — option A, B or C in §3.3. Blocking the "all standards enforced" goal.
2. **Authorization to change `app/`** — needed for §3.1 (security) and §3.4 (format).
3. **A `githooks/pre-commit`** — do we want commit-time enforcement, and does it replace or delegate
   to the `.pre-commit-config.yaml` framework? (§3.6)
4. **Tool-version source of truth** for CI vs local (§3.5).
5. **The intermittent repair benchmark** (§3.2) — authorize the `app/gamedev/` change, inject a
   deterministic reasoner, or accept a rate-measured benchmark permanently.

---

## 7. Why this document is not co-change bound

Every other doc in `docs.manifest.yaml` declares `covers` paths and is checked when those paths
change. This one deliberately declares `covers: []`.

Its subject is *open work*, which changes independently of any single file: closing item 3.1 changes
`app/tools/`, not this document's bookkeeping, and forcing a co-change here would produce a blocking
finding on every unrelated commit — the failure mode that gets a rule bypassed rather than followed.

The honesty cost is real and accepted: nothing will mechanically notice when this document goes
stale. Review it when the gate's interface changes or when an item above is closed, and delete
closed items rather than leaving them ticked.
