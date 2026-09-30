# Testing Strategy

> Companion: `software-testing` v0.1.0 from ProjectTemplates 0.1.0
> Answers here are this project's source of truth.
> Re-generate or adopt a newer template only as a deliberate decision (`tpl update`).

---

## Test levels and emphasis

| Level | Emphasis | Coverage target |
|-------|----------|-----------------|
| Unit (domain) | Rule/logic correctness, purity, determinism | ≥ 95% |
| Unit (brain/agents) | Socratic flow, evaluation, tool dispatch | ≥ 95% |
| Integration (adapters) | REST/SSE/WS contracts, auth, persistence | ≥ 85% |
| Sandbox security | Escape attempts, timeouts, resource caps | High (security-critical) |
| E2E (frontend) | Streaming render, voice smoke | Representative paths (Playwright, Phase 9) |
| Fault injection | Circuit-breaker failover, provider 429/503 | Deterministic scenarios |

## Priority of what must be tested vs light coverage

- **Must:** domain rules, safety gates, sandbox isolation, grounding/citation audits,
  circuit-breaker failover.
- **Light:** visual/styling details, non-critical config paths.

## Environments, fixtures, repeatability

- pytest with deterministic fixtures; seeded RNG where relevant; mock provider pool;
  fake LHS export fixture; CI runs everything fresh.

## Commands to run each level

```bash
.venv/bin/python -m pytest tests/             # all backend levels
.venv/bin/mypy app/                           # strict typecheck
.venv/bin/pre-commit run --all-files          # ruff, ruff-format, mypy, eof fixes
# frontend (Phase 7+, once `frontend/` exists): cd frontend && pnpm typecheck && pnpm lint
# Playwright E2E added in Phase 9
```

## Interpretation: code bug vs design bug

- A failing unit test in `app/domain/` = logic bug → fix code.
- A failing boundary/import check = layering violation → fix structure (or record ADR).
- A failing contract test against LHS export = schema drift → adapter fix, do not touch
  the canonical source.
- A test that is flaky/timing-dependent in E2E mode = design bug in test isolation.

---

## Enforcement: the local gate, and why CI is not the gate

**Branch protection is unavailable on this repository.** It is private, the owner is on the free
plan, and the GitHub API returns `403` for `branches/main/protection`:

> Upgrade to GitHub Pro or make this repository public to enable this feature.

This was verified rather than assumed. The consequence is blunt and worth stating plainly:
**CI cannot stop anything.** Thirty of thirty recent runs on `main` concluded `failure` and merges
proceeded anyway. A red pipeline here is a notification, not a barrier.

So enforcement lives locally, and CI is a **mirror** — its job is to confirm that what passed
locally also passes on a clean runner, never to be the first place a problem is discovered. If CI
finds something the local gate did not, that is a bug in the gate: add the missing stage rather than
depending on CI to notice.

### Running the gate

```bash
python3 scripts/ci_gate.py           # every stage
python3 scripts/ci_gate.py --quick   # docs + governance only
python3 scripts/ci_gate.py --list    # show stages
```

It is also wired into `githooks/pre-push`, which is installed with:

```bash
bash scripts/setup_hooks.sh
```

The hook runs the full gate before any ref leaves the machine, and **there is no bypass flag**.
`--no-verify` is not honoured. A gate you can talk your way out of is a suggestion, and with the
GitHub layer removed there is nothing behind this one.

### Coverage targets, and what actually enforces them

The table above states targets. For a target to mean anything it must be enforced, and an audit
found this repository documented **five** coverage standards while gating **one**. The current
state, measured:

| Scope | Documented | Measured | Enforced by | Status |
|-------|-----------|----------|-------------|--------|
| `app.domain` | ≥ 95% | 100.0% | `coverage-domain` stage, `ci.yml` | **Gated, met** |
| `app.brain` | ≥ 95% | 96.5% | `coverage-brain` stage | **Gated, met** |
| `app.adapters` | ≥ 85% | 67.5% | measured + reported only | **Gap — escalated** |
| `app.tools` | ≥ 95% | 83.3% | measured + reported only | **Gap — escalated** |
| `app` (whole) | — | 79.9% | `quality-ratchets.yml` (≥ 75%) | Gated |

`app.adapters` and `app.tools` are deliberately **not** gated yet. Gating a scope 10–15 points below
its documented floor would make the gate red for reasons unrelated to whatever is being pushed, and
a permanently-red gate is one people learn to bypass. They are measured and reported on a schedule
instead, and the discrepancy is escalated for a decision — raise the documented floor, raise the
coverage, or mark the target as aspirational. What is *not* acceptable is leaving a documented
standard that nothing enforces, because it reads as assurance and is not.

`scripts/docs/check_standard_reality.py` now fails the gate whenever a documented coverage
threshold has no enforcing gate. That is what stops this drifting back.

### Repeated-run verification

A check that has passed **once** has demonstrated it *can* pass. It has not demonstrated it *does*.
`scripts/verify_repeat.py` runs the enforcement surface N times and requires **N consecutive
passes**, writing a per-run log per check to `artifacts/verify-repeat/<timestamp>/`:

```bash
python3 scripts/verify_repeat.py --runs 3 --control
```

Its `--control` flag injects a genuine failure and asserts the harness detects it. Without that
control, "three consecutive passes" is an unfalsifiable claim — a harness that reports PASS for
everything is indistinguishable from a working one until the day it matters.

The nominated checks are the ones that decide whether *other* things pass: the manifest validator,
the standard-vs-reality checker, the executable-docs checker, the gate meta-tests, and the gate
itself. If one of those is flaky, every verdict it produces is suspect.

### Fault injection

The gate's own failure detection is tested, not assumed:

* `githooks/pre-push --self-test` runs a command that exits non-zero and asserts the hook notices.
* `tests/meta/test_enforcement_system.py` injects an unclassified doc, a duplicate manifest entry, a
  misspelled `staleness` value, a dead `covers` binding, a wrong doctest, and a syntax error, and
  asserts each is rejected. A guard that cannot fail is decoration.
* The manifest validator's universe includes **untracked** markdown, so a newly written doc cannot
  escape classification on the way in.

### The lint ratchet, and why not a plain format check

`ruff format --check` reports two pre-existing non-conformant files. A stage that fails on
pre-existing debt is a stage nobody can satisfy, so it gets ignored — which is precisely how this
repository accumulated thirty consecutive red CI runs that nobody read. But exempting those files is
worse: it converts a known problem into a permanent blind spot.

`scripts/ratchet.py` resolves this with three rules:

1. A violation **not** in the baseline **fails**. You cannot introduce new non-conformance.
2. A violation **in** the baseline is **reported**, not failed. Existing debt stays visible.
3. A baseline entry that **no longer violates** also **fails**, as *stale*.

Rule 3 is what makes it a ratchet rather than a permanent exemption, and it is the rule most
implementations omit. Without it a baseline only ever grows: someone fixes a file, forgets the
entry, and the exemption outlives the problem. With it, the list can only shrink and its length is a
real measure of remaining debt.

```bash
python3 scripts/ratchet.py format            # check
python3 scripts/ratchet.py format --update   # re-record — review the diff before committing
```

The baseline currently holds one file, `app/skills/builtin.py`. It is **not** reformatted in this
change on purpose: `ruff format` rewrites 339 lines of semantically-neutral code there, which is far
too large a diff to fold into a tooling change, and formatting it is a decision someone should make
deliberately rather than inherit. The ratchet keeps it visible until then.

### Lint scope

The lint and format stages pass `--exclude "*.sh"`. Ruff walks the paths it is given and, without
this, attempts to parse shell scripts — producing parse errors that read like lint failures. A gate
whose output contains noise that is not actionable trains people to skim it.

Formatting fixes applied to make the gate satisfiable were **whitespace-only**: a missing trailing
newline in `app/authority/__init__.py`, `scripts/verify.py` and `scripts/verify_git_safety.py`, and
trailing whitespace in `app/routers/chat.py`. Verified with `git diff -w` showing no non-whitespace
change in any of them.

### How the coverage stages are judged, and why not by exit code

These layers carry the repository's 12 pre-existing test failures, so `--cov-fail-under` reaching
its floor and pytest exiting non-zero happen **at the same time**: coverage passes, a test fails,
pytest returns 1. Keying the stage on that exit code reports a coverage failure that is really a
test failure — the same defect counted twice, with the coverage number rendered unusable exactly
when someone wants to read it. (pytest-cov 7.1.0 offers no `--cov-ignore-errors`.)

So the coverage stages write a JSON report (`--cov-report=json:coverage.json`) and the gate reads
`totals.percent_covered` from it, which is exact and independent of test outcomes. Nothing is
hidden by this:

* a missing or unparseable report is a stage **failure** (exit 5);
* the `expect` guard still requires the visible `TOTAL` row, so a stage cannot pass while producing
  no evidence;
* the test failures themselves are reported in full by the `tests` stage, which is where they
  belong — you see each one once, not twice.

The advisory adapter and tools stages are non-blocking by design and never inherit an exit code from
either direction. Their purpose is to keep a documented-but-unmet number in front of people, not to
add a second red stage that people learn to skim past.

**Measuring these numbers.** The figures in the table above come from a single-scope
`--cov=<scope>` run inside the gate. An earlier aggregate over the whole suite reported 69.6% and
85.1% for adapters and tools; the difference is the measurement method, not a regression. The gate's
own figures are now the ones quoted in `AGENTS.md` and `docs/RULES.md`, so the documented number and
the enforced number cannot drift apart.

### Declared defects: visible debt, not hidden failures

The gate found two genuine product defects, neither caused by the work that built it:

1. **12 failing tests** — 8 in `tests/unit/authority/`, 3 in `tests/unit/knowledge/`
   (`TestLHSSchemaContract`, asserted against the real LearningHubSTEM export, which has drifted),
   and 1 in `tests/unit/voice/` that performs a live network download.
2. **5 tools under `app/tools/` without `@safety_gate`**, which `scripts/board/review.py` reports on
   the unmodified tree. This one is security-relevant and is the highest-priority item on the list.

Both need `app/` changes to fix. A gate that stays red on defects nobody is currently fixing is a
gate people learn to ignore — that is exactly how this repository reached thirty consecutive red CI
runs that nobody read. But deleting the failures from the gate would be far worse.

So `scripts/declared_defects.py` declares them, by name, in a file whose diff is reviewable:

| Situation | Gate result |
|---|---|
| Failure is declared | Reported as **DECLARED**; does not fail the gate. **Still printed, every run, by name.** |
| Failure is **not** declared | **Fails the gate.** New breakage is never absorbed. |
| A declaration **no longer reproduces** | **Fails the gate, as stale.** A fixed defect must be removed. |

The third rule is what makes this a ratchet rather than a suppression list — the same rule
`scripts/ratchet.py` and `scripts/verify_repeat.py` apply, deliberately. The list can only shrink,
and its length is a real measure of open, accepted debt.

Three properties keep this honest, and all three are tested rather than assumed:

* **Nothing is skipped.** Every declared failure is still detected, still counted, and still printed
  on every run — pass or fail. It is *classified*, not hidden.
* **A declaration must be real.** A meta-test asserts each declared board defect actually appears in
  the gate's output. A declaration that excuses nothing while appearing to is worse than none.
* **Visibility is verified.** `scripts/verify_repeat.py` refuses to call a check verified if it
  passes while its declared defects stop being reported. A declaration nobody can see is a
  suppression wearing a declaration's clothes.

Proven, not asserted — a genuine new failure was injected and the gate refused it:

```
$ # inject a failing test
$ python3 scripts/ci_gate.py --stage tests
  exit=1  1 UNDECLARED test failure(s) — new breakage is never absorbed
          + tests/meta/test_ratchet_probe.py::test_genuine_new_breakage
$ # remove it
$ python3 scripts/ci_gate.py --stage tests
  exit=0  12 declared, still-open test failure(s); 0 undeclared.
```

**Fixing these defects is product work and is escalated, not assumed.** The gate is not the place to
fix them, and neither is this document.

### Running the whole thing

```bash
python3 scripts/ci_gate.py                        # all 14 stages
bash githooks/pre-push --self-test                # prove the hook can refuse a push
python3 scripts/verify_repeat.py --runs 3 --control   # N consecutive passes, with a control
bash scripts/setup_hooks.sh                       # install (idempotent; --check reports state)
```

### Executable documentation

A documented example that has never been run is a claim, not a test. It goes stale the moment a
signature changes, and nothing notices — the reader finds out, not the author.

So examples in this repository are executed. Two forms are recognised:

* a fenced `python` block preceded by `<!-- name: test_something -->` is **run as a test** — its
  assertions must hold;
* a fenced block containing `>>>` is **run as a doctest**, exactly as in a docstring.

The checker reports blocks *by how they were verified* — executed, doctested, compiled-only, or
skipped — so the summary can never imply more than was actually done. An earlier version of this
system (in the repository whose docs governance this is modelled on) promised runnable snippets in a
`docs/snippets/` directory that was never created, so every one of its markdown blocks was only
`compile()`d. That never catches a bad import: `compile()` is satisfied by
`from app.adapters import http_router` even when no such export exists. The distinction is not
pedantic; it is the difference between a checked example and a decorative one.

The examples below are executed on every gate run.

<!-- name: test_domain_layer_is_import_pure -->
```python
# AGENTS.md 3.4: the domain layer is pure Python with no framework imports.
# This is the rule most likely to rot, because the import that breaks it looks harmless.
import ast
import pathlib

FORBIDDEN = ("fastapi", "starlette", "pydantic", "requests", "httpx")
root = pathlib.Path("app") / "domain"
offenders = []
for path in root.rglob("*.py"):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        for name in names:
            if name.split(".")[0] in FORBIDDEN:
                offenders.append(f"{path}: {name}")

assert not offenders, f"domain layer imports a framework: {offenders}"
```

<!-- name: test_api_key_comparison_is_constant_time -->
```python
# The auth dependency must compare secrets in constant time; `==` leaks length and prefix through
# timing. Asserting the *implementation* rather than the behaviour is deliberate: the behaviour is
# identical either way, so only an implementation check catches the regression.
import inspect

from app.adapters.auth import require_api_key

source = inspect.getsource(require_api_key)
assert "compare_digest" in source, "require_api_key no longer compares keys in constant time"
```

The example above is the one that matters, and it is worth saying why it is written as a test rather
than as prose. The first two drafts of it were wrong: they imported `app.auth`, then
`verify_password`. Both mistakes are *invisible* to a `compile()`-only check — the import statement
parses perfectly. Only executing the block found them, which is the entire argument for executing
documentation instead of parsing it.

<!-- name: test_manifest_classifies_every_doc -->
```python
# The docs policy is enforced, not aspirational: every markdown file must be classified exactly
# once. This example asks the same question the gate does, so a reader can reproduce the verdict.
import subprocess
import sys

proc = subprocess.run(
    [sys.executable, "scripts/docs/manifest_validate.py", "--quiet"],
    capture_output=True,
    text=True,
)
assert proc.returncode == 0, f"manifest invalid:\n{proc.stdout}\n{proc.stderr}"
```

A doctest, for comparison — this one is executed rather than compiled:

```python
>>> from app.domain.learner import LearnerState
>>> LearnerState(learner_id="demo").learner_id
'demo'
```
