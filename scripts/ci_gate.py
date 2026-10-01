#!/usr/bin/env python3
"""The PROFESSOR-J gate — run everything locally, before anything reaches GitHub.

WHY THIS EXISTS
---------------
Branch protection is **not available** on this repository: it is private, the owner is on the free
plan, and the GitHub API returns 403 for `branches/main/protection` with the message *"Upgrade to
GitHub Pro or make this repository public to enable this feature."* That was verified, not assumed.

The consequence is blunt: **CI cannot stop anything.** A red pipeline is a notification, not a
barrier. Thirty of thirty recent runs on `main` concluded `failure` and merges proceeded regardless.

So the gate moves here. This script is the enforcement point. GitHub Actions runs the same stages as
a *mirror* — its job is to confirm that what passed locally also passes on a clean runner, never to
be the first place a problem is discovered. If CI finds something this gate did not, that is a bug
in this gate, and the fix is to add the missing stage here rather than to rely on CI noticing.

DESIGN RULES
------------
1. **No bypass.** There is no `--skip`, no `--force`, no environment escape hatch. A gate you can
   talk your way out of is a suggestion. Fixing a false positive means fixing the check.
2. **Every stage runs.** The runner does not stop at the first failure. You get the complete list
   of what is wrong in one pass, because a gate that reveals problems one at a time trains people
   to bypass it.
3. **Failures are explained.** Each failure prints the exact command, its exit code, and the tail
   of its output, so the fix is obvious without re-running anything.
4. **No stage silently passes.** A stage whose command cannot run at all (missing binary) is a
   FAILURE, not a skip. "Tool not found" must never read as "check passed".
5. **Docs are a first-class stage, not an afterthought.** They are also the stage most likely to
   be quietly dropped, so they are listed explicitly and cannot be disabled.

Usage:
    python3 scripts/ci_gate.py                 # every stage
    python3 scripts/ci_gate.py --stage docs    # one stage (for iterating while fixing)
    python3 scripts/ci_gate.py --list          # show stages without running
    python3 scripts/ci_gate.py --json          # machine-readable summary (for the meta-gate)

Exit codes:
    0  every stage passed
    1  at least one stage failed
    2  the gate itself is misconfigured (e.g. a stage names a script that does not exist)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from declared_defects import (  # noqa: E402
    DECLARED_BOARD_DEFECTS,
    DECLARED_TEST_FAILURES,
    declared_board_markers,
    declared_failure_ids,
)

VENV_PY = REPO_ROOT / ".venv" / "bin" / "python"


def _py() -> str:
    """Prefer the repository venv; fall back to the interpreter running this script.

    Falling back is deliberate: the gate must be runnable from a fresh clone or from CI, where
    `.venv` may not exist yet. Never silently skip on a missing interpreter.
    """
    return str(VENV_PY) if VENV_PY.exists() else sys.executable


@dataclass
class Stage:
    """One check. `required` is always True in practice; the field exists so that a genuinely
    advisory check must be *labelled* advisory and shows up as such in the summary rather than
    hiding among the passes."""

    key: str
    title: str
    cmd: list[str]
    required: bool = True
    # Substring that must appear in output for the stage to count as having actually run. Guards
    # against a command that exits 0 while doing nothing — the failure mode this whole audit is
    # about. Empty means "exit code is sufficient".
    expect: str = ""
    docs: str = ""
    # Enforce a coverage floor by reading coverage.py's JSON report, instead of relying on
    # `--cov-fail-under` plus pytest's exit code.
    #
    # WHY: this repository has 9 pre-existing test failures spanning the layers these coverage
    # stages measure. `--cov-fail-under` reports "Required test coverage reached" and pytest STILL
    # exits 1, because a test failed. Keying the stage on that exit code reports a coverage failure
    # that is really a test failure — the same defect counted twice, and the coverage number made
    # unusable exactly when you want to read it. (pytest-cov 7.1.0 has no `--cov-ignore-errors`.)
    #
    # Reading the JSON report gives the exact percentage regardless of test outcomes. It hides
    # nothing: a missing or unparseable report is a stage FAILURE, and the test failures themselves
    # are reported in full by the `tests` stage.
    coverage_floor: float = 0.0
    coverage_scope: str = ""
    # Classify failures against the declared-defect baseline (scripts/declared_defects.py) instead
    # of failing on any non-zero exit. Declared failures are still printed every run; undeclared
    # ones fail the stage, and a declaration that stops reproducing fails as STALE. This is a
    # ratchet, not a skip list — see that module for the full contract.
    classify_tests: bool = False
    classify_board: bool = False


@dataclass
class Result:
    key: str
    title: str
    required: bool
    exit_code: int
    duration_s: float
    output_tail: str = ""
    note: str = ""

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


@dataclass
class GateReport:
    results: list[Result] = field(default_factory=list)

    @property
    def failed(self) -> list[Result]:
        return [r for r in self.results if not r.ok and r.required]

    @property
    def ok(self) -> bool:
        return not self.failed


def build_stages(*, quick: bool = False, docs_range: str = "") -> list[Stage]:
    """The stage list. Order is deliberate: cheapest and most-often-wrong first, so a typo fails
    in two seconds instead of after a ninety-second test run.

    `docs_range` selects how the co-change stage compares docs to code — see that stage below.
    """
    py = _py()
    stages = [
        Stage(
            key="docs-manifest",
            title="Docs manifest — every doc classified exactly once",
            cmd=[py, "scripts/docs/manifest_validate.py"],
            docs="R4a completeness, R4b vocabulary, R4c every code binding resolves.",
        ),
        Stage(
            key="docs-structure",
            title="Docs structure — headings, fences, links, drift markers",
            cmd=[py, "scripts/docs/check_docs.py", "--worktree"],
            docs="Markdown structure, internal links, drift markers, standalone dates.",
        ),
        Stage(
            key="docs-exec",
            title="Docs executable examples — doctests and .md code blocks",
            cmd=[py, "scripts/docs/check_executable.py"],
            docs=(
                "Runs >>> examples in Python docstrings and fenced python blocks in markdown. "
                "A doc example that does not run is a doc that lies."
            ),
        ),
        Stage(
            key="docs-standard-reality",
            title="Docs standard vs reality — documented claims that are not true",
            cmd=[py, "scripts/docs/check_standard_reality.py", "--worktree"],
            docs=(
                "Detects the class of defect where a doc states a threshold the code does not "
                "meet. Added after AGENTS.md claimed >=85% adapter coverage while measured was 68%."
            ),
        ),
        Stage(
            key="docs-code-cochange",
            title="Docs-to-code co-change — code changed without its doc",
            # WHICH COMPARISON, AND WHY IT MATTERS
            #
            # `--full` compares the WORKTREE to HEAD. That is correct while you are working, and it
            # is what makes the check useful in an editor. But at PUSH TIME the tree is normally
            # clean — everything has just been committed — so `--full` finds no differences and the
            # check passes *vacuously*. A gate stage that inspects nothing is worse than no stage,
            # because it reports a pass.
            #
            # `--range A..B` compares the two COMMITS instead, which is the question that actually
            # matters before a push: "across the commits I am about to publish, did any code change
            # go out without its document?" The hook therefore passes the range it is pushing.
            #
            # The fallback to `--full` is for local runs, where there is no meaningful range yet.
            cmd=(
                [py, "scripts/docs/check_changed.py", "--range", docs_range]
                if docs_range
                else [py, "scripts/docs/check_changed.py", "--full"]
            ),
            docs=(
                "R1: a change under a doc's `covers` paths without a change to that doc, and "
                "without an explicit `Docs-Not-Needed:` trailer, fails. Compares commits when a "
                "range is supplied (a push), the worktree otherwise (local use)."
            ),
        ),
        Stage(
            key="lint",
            title="Lint ratchet (ruff check, no new violations)",
            cmd=[py, "scripts/ratchet.py", "lint"],
            docs=(
                "Read-only lint wrapped in a baseline ratchet: fails on any NEWLY violating file "
                "and also fails if a baselined file stops violating, so the baseline can only "
                "shrink. A plain `ruff check` surfaces 5 pre-existing offenders (concentrated in "
                "app/skills/builtin.py) and would be permanently red."
            ),
        ),
        Stage(
            key="format",
            title="Format ratchet (ruff format --check, no new violations)",
            cmd=[py, "scripts/ratchet.py", "format"],
            docs=(
                "Read-only format check wrapped in a baseline ratchet. It fails on any NEWLY "
                "non-conformant file and ALSO fails if a baselined file stops violating, so the "
                "baseline can only shrink. A plain `ruff format --check` was rejected here: it "
                "reports 2 pre-existing files, and a permanently-red stage is one people learn to "
                "ignore. `pre-commit run --all-files` was also rejected — it REWRITES the tree."
            ),
        ),
        Stage(
            key="mypy",
            title="Type check (mypy, strict)",
            cmd=[py, "-m", "mypy", "app/", "tests/", "scripts/"],
            docs="Strict typing across app, tests and scripts.",
        ),
        Stage(
            key="tests",
            title="Test suite",
            cmd=[
                py,
                "-m",
                "pytest",
                "tests/",
                "-q",
                "--tb=short",
                # Tests marked `nondeterministic_repair` assert a PROBABILISTIC outcome of the
                # model-backed repair loop. A gate that fails ~20% of the time for reasons
                # unrelated to the change under test is a gate people learn to bypass, which is
                # strictly worse than a smaller deterministic one. They are deselected here and
                # measured by the nightly repeated-run job, which reports the actual rate.
                # This is a controlled deselection, not a skip: the marker and its reason are
                # registered in pyproject.toml, and the count of deselected tests is printed.
                "-m",
                "not nondeterministic_repair",
            ],
            classify_tests=True,
            docs=(
                "The deterministic suite. Failures are classified against "
                "scripts/declared_defects.py: the known-open failures do not fail the gate, any "
                "OTHER failure does, and a declaration that stops reproducing fails as stale. "
                "Nothing is skipped — every declared failure is still detected and printed by "
                "name on every run. Tests that assert probabilistic outcomes are deselected by "
                "marker and measured by the nightly repeated-run job instead."
            ),
        ),
        Stage(
            key="coverage-domain",
            title="Domain coverage floor (>=95%)",
            cmd=[
                py,
                "-m",
                "pytest",
                "tests/unit/domain/",
                "-q",
                "--tb=short",
                "--cov=app.domain",
                "--cov-report=term-missing",
                "--cov-fail-under=95",
            ],
            docs="The one coverage gate that was already load-bearing. Kept.",
        ),
        # ── Whole-suite coverage, judged on COVERAGE ONLY ───────────────────────────────────
        # These stages span layers whose tests include the 9 pre-existing failures (8 authority,
        # 3 LHS contract, 1 voice). `--cov-fail-under` reports "Required test coverage reached" and
        # pytest STILL exits 1, because a test failed. Keying the stage on pytest's exit code would
        # therefore report a coverage failure that is really a test failure — the same defect
        # counted twice, with the coverage number made unusable in the process.
        #
        # So the verdict comes from coverage.py's own marker, and `--ignore_errors` stops False
        # from becoming an exit code. This hides nothing: a genuinely broken environment or a
        # collection error makes coverage.py print neither marker, which the `expect` guard below
        # turns into a stage FAILURE. The test failures themselves are reported, in full, by the
        # `tests` stage above.
        #
        # ── Documented coverage standards, now enforced where they are already met ──────────
        # An audit found this repository documents FIVE coverage standards and gated ONE:
        #
        #   app.domain   documented >= 95%   measured 100.0%   was gated  -> kept
        #   app.brain    documented >= 95%   measured  98.5%   NOT gated  -> gated below
        #   app.adapters documented >= 85%   measured  69.6%   NOT gated  -> reported, escalated
        #   app.tools    documented >= 95%   measured  85.1%   NOT gated  -> reported, escalated
        #
        # A documented guarantee that nothing enforces is worse than no guarantee: it reads as
        # assurance and is not. `scripts/docs/check_standard_reality.py` now fails when a documented
        # threshold has no gate, so this drift cannot recur silently.
        #
        # adapters and tools are NOT gated yet. Gating a scope 10-15 points below its documented
        # floor would make the gate red for reasons unrelated to whatever is being pushed, and a
        # gate that is always red is a gate people learn to bypass. They are measured and reported
        # by .github/workflows/quality-ratchets.yml; the gap is escalated for a human decision.
        Stage(
            key="coverage-brain",
            title="Brain coverage floor (>=95%, as documented)",
            cmd=[
                py,
                "-m",
                "pytest",
                "tests/",
                "-q",
                "--tb=short",
                "-p",
                "no:warnings",
                "--cov=app.brain",
                "--cov-report=term-missing",
                "--cov-report=json:coverage.json",
            ],
            # Judged on MEASURED coverage, not pytest's exit code — see the coverage_floor field.
            coverage_floor=95.0,
            coverage_scope="app.brain",
            docs=(
                "AGENTS.md:86 and docs/RULES.md:37 both state >=95% for the cognitive engine. "
                "Measured 98.5%, so this turns a documented guarantee into an enforced one at no "
                "new cost."
            ),
        ),
        Stage(
            key="coverage-adapters-measured",
            title="Adapter coverage (documented 85%, actual 69.6%) — reported",
            cmd=[
                py,
                "-m",
                "pytest",
                "tests/",
                "-q",
                "--tb=no",
                "-p",
                "no:warnings",
                "--cov=app.adapters",
                "--cov-report=term-missing",
                "--cov-report=json:coverage.json",
            ],
            required=False,
            # Advisory stages still must produce their evidence: a missing TOTAL row would mean the
            # recommendation rests on nothing, which is worse than reporting no number at all.
            expect="TOTAL",
            coverage_scope="app.adapters",
            docs=(
                "Documented standard >= 85% (AGENTS.md:87, docs/RULES.md:37); measured 69.6%. "
                "Advisory: reported, never folded into the pass count."
            ),
        ),
        Stage(
            key="coverage-tools-measured",
            title="Tools coverage — measured and reported (documented 95%, actual 85.1%)",
            cmd=[
                py,
                "-m",
                "pytest",
                "tests/",
                "-q",
                "--tb=no",
                "-p",
                "no:warnings",
                "--cov=app.tools",
                "--cov-report=term-missing",
                "--cov-report=json:coverage.json",
            ],
            required=False,
            expect="TOTAL",
            coverage_scope="app.tools",
            docs=(
                "docs/500-software-testing.md:14 states >=95%; measured 85.1%. app/tools holds the "
                "sandbox execution path, so this is the higher-risk of the two gaps and is ranked "
                "first for remediation. Advisory: reported, never folded into the pass count."
            ),
        ),
        Stage(
            key="governance-board",
            title="Governance board checks",
            cmd=[py, "scripts/board/review.py"],
            classify_board=True,
            expect="checks passed",
            docs=(
                "scripts/board/review.py. Genuinely fails locally and had NEVER run in CI because "
                "its job was gated behind two always-failing jobs. Running it here makes it real."
            ),
        ),
    ]
    if quick:
        keys = {"docs-manifest", "docs-structure", "docs-standard-reality", "governance-board"}
        stages = [s for s in stages if s.key in keys]
    return stages


# ── runner ───────────────────────────────────────────────────────────────────


def run_stage(stage: Stage, *, verbose: bool = False) -> Result:
    start = time.monotonic()
    missing = _missing_targets(stage)
    if missing:
        return Result(
            key=stage.key,
            title=stage.title,
            required=stage.required,
            exit_code=2,
            duration_s=0.0,
            note=f"stage cannot run: {missing} does not exist",
            output_tail="",
        )

    env = dict(os.environ)
    # Keep output deterministic and unbuffered so the captured tail is the real tail.
    env["PYTHONUNBUFFERED"] = "1"
    try:
        proc = subprocess.run(
            stage.cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            env=env,
            timeout=stage_timeout(stage),
        )
    except subprocess.TimeoutExpired:
        return Result(
            key=stage.key,
            title=stage.title,
            required=stage.required,
            exit_code=124,
            duration_s=time.monotonic() - start,
            note=f"timed out after {stage_timeout(stage)}s",
        )
    except FileNotFoundError as exc:
        return Result(
            key=stage.key,
            title=stage.title,
            required=stage.required,
            exit_code=127,
            duration_s=time.monotonic() - start,
            note=f"command not found: {exc}",
        )

    combined = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    code = proc.returncode
    note = ""

    # Classify against the declared-defect baseline. Every declared defect is still detected and
    # still reported by name; only undeclared failures fail the stage.
    if stage.classify_tests:
        observed = _failing_test_ids(combined)
        declared = declared_failure_ids()
        undeclared = sorted(observed - declared)
        stale = sorted(declared - observed)
        if undeclared:
            code = 1
            note = (
                f"{len(undeclared)} UNDECLARED test failure(s) — new breakage is never absorbed:\n"
                + "\n".join(f"          + {t}" for t in undeclared[:10])
            )
        elif stale:
            code = 1
            note = (
                f"{len(stale)} declared failure(s) no longer fail — the baseline is stale and must "
                f"be tightened:\n" + "\n".join(f"          - {t}" for t in stale[:10])
            )
        elif observed:
            code = 0
            note = (
                f"{len(observed)} declared, still-open test failure(s); 0 undeclared. "
                f"See scripts/declared_defects.py"
            )
        else:
            code = 0
            note = "no failures"

    if stage.classify_board:
        declared_markers = declared_board_markers()
        present = sorted(m for m in declared_markers if m in combined)
        absent = sorted(declared_markers - set(present))
        # Any FAIL line the board prints that is not explained by a declaration is new breakage.
        unexplained = [
            line.strip()
            for line in combined.splitlines()
            if "FAIL " in line and not any(m.split(":")[0] in line for m in declared_markers)
        ]
        if unexplained:
            code = 1
            note = f"{len(unexplained)} undeclared board failure(s): " + "; ".join(unexplained[:3])
        elif absent:
            code = 1
            note = (
                "declared board defect(s) no longer reported — the baseline is stale: "
                + "; ".join(absent[:3])
            )
        elif present:
            code = 0
            note = f"{len(present)} declared, still-open board defect(s); 0 undeclared."
        else:
            code = 0
            note = "all board checks passed"

    # A coverage stage is judged on MEASURED COVERAGE, not on pytest's exit code. See the
    # `coverage_floor` field for why those differ in this repository.
    if stage.coverage_floor or stage.coverage_scope:
        measured, why = _measured_coverage(stage.coverage_scope)
        if measured is None:
            code = 5
            note = f"could not read a coverage report for {stage.coverage_scope}: {why}"
        elif stage.coverage_floor and measured + 1e-9 < stage.coverage_floor:
            code = 1
            note = (
                f"MEASURED {measured:.2f}% for {stage.coverage_scope}, below the documented floor "
                f"of {stage.coverage_floor:.0f}%. Raise coverage or revise the standard."
            )
        elif not stage.coverage_floor:
            # Advisory: no floor, so the measurement is the deliverable. It must not change the
            # exit code either way — reaching here proves the report was readable, and the `expect`
            # guard below still requires the visible evidence. This stage's purpose is to keep a
            # documented-but-unmet number in front of people, not to add a second red stage.
            code = 0
            note = f"measured {measured:.2f}% for {stage.coverage_scope} (advisory, no floor)"
        else:
            # Floor met. The exit code IS forced to 0, and only because the `expect` guard below
            # still runs: a stage that met its floor while producing no visible evidence cannot
            # pass silently. pytest's non-zero exit here means a test failed, and every test
            # failure is reported in full by the `tests` stage — inheriting it would report the
            # same defect twice and turn a met floor into a red stage.
            code = 0
            note = (
                f"measured {measured:.2f}% for {stage.coverage_scope}, floor "
                f"{stage.coverage_floor:.0f}% — met"
            )
            if proc.returncode != 0:
                note += (
                    f" (pytest exited {proc.returncode} on pre-existing test failures, reported "
                    f"by the `tests` stage)"
                )
    # A stage that exits 0 without producing its expected marker has not actually run. This is
    # the "tool self-check" rule: a mutation/fuzz/coverage tool reporting success while doing
    # zero work is indistinguishable from a real pass unless you demand evidence it ran.
    if code == 0 and stage.expect and stage.expect not in combined:
        code = 3
        note = f"exited 0 but output never contained {stage.expect!r} — did it actually run?"

    return Result(
        key=stage.key,
        title=stage.title,
        required=stage.required,
        exit_code=code,
        duration_s=time.monotonic() - start,
        output_tail=_tail(combined, 60 if verbose else 25),
        note=note,
    )


def _failing_test_ids(output: str) -> set[str]:
    """Extract pytest node IDs from a `-q --tb=short` run.

    Reads both the `FAILED <id>` short-summary lines and the `-q` progress markup, so the set is
    complete whether or not the short summary was truncated by the gate's output tail.
    """
    ids: set[str] = set()
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("FAILED "):
            # A pytest node ID contains no whitespace, so the first token is the ID.
            # Splitting on " - " instead would truncate IDs at any embedded dash.
            node = stripped[len("FAILED ") :].split()[0]
            if "::" in node:
                ids.add(node)
    return ids


def _measured_coverage(scope: str) -> tuple[float | None, str]:
    """Read the total coverage percentage for `scope` from coverage.py's JSON report.

    Returns (percentage, reason-when-absent). The percentage counts lines AND branches, matching
    how coverage.py computes its own total, so it is directly comparable to `--cov-fail-under`.
    """
    report = REPO_ROOT / "coverage.json"
    if not report.exists():
        return None, "coverage.json was not produced (did pytest run with --cov-report=json?)"
    try:
        data = json.loads(report.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return None, f"coverage.json unreadable: {exc}"
    totals = data.get("totals") or {}
    value = totals.get("percent_covered")
    if value is None:
        return None, "coverage.json has no totals.percent_covered"
    try:
        return float(value), ""
    except (TypeError, ValueError):
        return None, f"totals.percent_covered is not a number: {value!r}"


def stage_timeout(stage: Stage) -> int:
    return 1200 if stage.key.startswith(("tests", "coverage-")) else 300


def _missing_targets(stage: Stage) -> str:
    """A stage whose script does not exist must FAIL, not pass vacuously."""
    for part in stage.cmd:
        if "/" in part and part.endswith(".py") and not Path(REPO_ROOT / part).exists():
            return part
    return ""


def _tail(text: str, lines: int) -> str:
    stripped = text.strip().splitlines()
    return "\n".join(stripped[-lines:])


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="PROFESSOR-J gate — run everything locally.")
    parser.add_argument("--stage", action="append", default=[], help="run only these stages")
    parser.add_argument("--list", action="store_true", help="list stages and exit")
    parser.add_argument("--json", dest="as_json", action="store_true", help="emit JSON summary")
    parser.add_argument("--quick", action="store_true", help="docs + governance only")
    parser.add_argument(
        "--docs-range",
        default="",
        metavar="A..B",
        help=(
            "check docs-to-code co-change across these commits instead of the worktree. The hook "
            "passes the range being pushed; without it the check compares worktree to HEAD, which "
            "passes vacuously on a clean tree."
        ),
    )
    parser.add_argument("--verbose", action="store_true", help="longer output tails")
    args = parser.parse_args(argv)

    stages = build_stages(quick=args.quick, docs_range=args.docs_range)
    if args.stage:
        wanted = set(args.stage)
        unknown = wanted - {s.key for s in stages}
        if unknown:
            print(f"unknown stage(s): {', '.join(sorted(unknown))}", file=sys.stderr)
            print(f"known: {', '.join(s.key for s in stages)}", file=sys.stderr)
            return 2
        stages = [s for s in stages if s.key in wanted]

    if args.list:
        for s in stages:
            print(f"{s.key:22} {s.title}")
        return 0

    report = GateReport()
    if not args.as_json:
        print("=" * 78)
        print("PROFESSOR-J GATE — local enforcement before anything reaches GitHub")
        print("=" * 78)
        print(f"Running {len(stages)} stage(s). All stages run; none stop the others.\n")

    for stage in stages:
        if not args.as_json:
            print(f"→ {stage.title} …", flush=True)
        result = run_stage(stage, verbose=args.verbose)
        report.results.append(result)
        if not args.as_json:
            mark = "PASS" if result.ok else "FAIL"
            print(f"  [{mark}] {result.duration_s:.1f}s")
            if not result.ok:
                if result.note:
                    print(f"  {result.note}")
                print(f"  $ {' '.join(stage.cmd)}")
                if result.output_tail:
                    for line in result.output_tail.splitlines():
                        print(f"  │ {line}")
                print()

    if args.as_json:
        print(json.dumps([asdict(r) for r in report.results], indent=2))
        return 0 if report.ok else 1

    print("=" * 78)
    total = len(report.results)
    passed = sum(1 for r in report.results if r.ok)
    advisory_failed = [r for r in report.results if not r.required and not r.ok]
    if advisory_failed:
        print("ADVISORY (not blocking, reported as failures not passes):")
        for r in advisory_failed:
            print(f"  REPORT {r.key:32} {r.title}")
        print()

    # Declared defects are printed on EVERY run, pass or fail. This is what separates a declared
    # defect from a hidden one: the failure is not in the stage results, so if it were not printed
    # here it would be invisible — and an invisible exemption is indistinguishable from a
    # suppression. A reviewer reading a green gate can see exactly what is being excused.
    if declared_failure_ids() or declared_board_markers():
        print("DECLARED DEFECTS (known, open, NOT hidden — still detected every run):")
        for node_id, reason in sorted(DECLARED_TEST_FAILURES):
            print(f"  TEST   {node_id}")
            print(f"         → {reason}")
        for marker, reason in sorted(DECLARED_BOARD_DEFECTS.items()):
            print(f"  BOARD  {marker}")
            print(f"         → {reason}")
        print("  Declared by scripts/declared_defects.py. A new failure fails the gate; a")
        print(
            "  declaration that stops reproducing fails the gate as stale. This list only shrinks."
        )
        print()
    if report.ok:
        print(f"GATE PASSED — {passed}/{total} stage(s)")
        print("=" * 78)
        return 0

    print(f"GATE FAILED — {passed}/{total} stage(s) passed, {len(report.failed)} failed")
    print("=" * 78)
    for r in report.failed:
        print(f"  FAIL  {r.key:22} {r.title}")
    print()
    print("Fix every failure above, then re-run. There is no bypass flag by design.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
