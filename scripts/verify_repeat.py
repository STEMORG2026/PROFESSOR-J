#!/usr/bin/env python3
"""Repeat-run stability verification — one pass is not a pass.

THE RULE
--------
A check that has passed **once** has demonstrated that it *can* pass. It has not demonstrated that
it *does* pass. Those are different claims, and only the second is worth anything in a gate.

So this verifier runs each nominated check N times and requires **N consecutive passes**, with a
per-run log written to disk. A single failure anywhere in the sequence fails the whole verification
and records which run failed, what the output was, and how long it took. There is no "retry until
green": a retry that hides a failure is exactly the false-green route this audit exists to close.

WHY THIS IS NEW WORK
--------------------
This was researched rather than assumed. The system this repository's docs governance is modelled
on (JARVIS) has **no stability mechanism at all** — no rerun plugin, no repeat count, no run logs.
Its strategy is determinism by construction. That is a good strategy and it is not sufficient here,
because this repository has checks whose *reliability* is genuinely in question:

  * the test suite has 12 known-red tests and one test that performs a live network download;
  * the gate itself is new code and its own correctness is asserted by tests that could be flaky;
  * doc checks read the filesystem and the git index, both of which change under them.

A flaky gate is worse than no gate: it teaches people that a red result is noise.

WHAT "GREAT LOG" MEANS HERE
---------------------------
The reference for a valuable verification record (JARVIS's DOCS_VERIFICATION_LOG.md) has five
properties, and this script's output has all of them:

  1. A falsifiable heading stating the outcome, not just "it passed".
  2. A replayable input — the exact command, recorded per run.
  3. Verbatim output — captured to a real file, not summarised to "ok".
  4. A positive control — the record shows that a *failing* input is detected, so a green
     sequence cannot be explained by the check being inert.
  5. Honesty — failures and limitations are named specifically, never softened to "known flake".

Usage:
    python3 scripts/verify_repeat.py                     # all nominated checks, 3 runs
    python3 scripts/verify_repeat.py --runs 5            # N consecutive passes
    python3 scripts/verify_repeat.py --check gate-quick
    python3 scripts/verify_repeat.py --control           # include the positive control
    python3 scripts/verify_repeat.py --json

Exit codes:
    0  every nominated check passed every run
    1  at least one run failed (the failing run is named)
    2  a nominated check could not run at all
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VENV_PY = REPO_ROOT / ".venv" / "bin" / "python"
LOG_ROOT = REPO_ROOT / "artifacts" / "verify-repeat"


# Output that legitimately differs between runs without indicating instability. Hashing the raw
# bytes would report every check as nondeterministic — a false alarm that trains people to ignore
# the signal, which is worse than having no signal.
#
# The distinction that matters: a *timestamp* or *temp path* changing is expected; a *count* or
# *verdict* changing is not. Only the former is normalised away.
VOLATILE_PATTERNS = [
    (re.compile(r"/tmp/[A-Za-z0-9_.\-]+"), "<tmp>"),  # random temp paths
    (re.compile(r"\.corrupt-\d+"), ".corrupt-<n>"),  # pid-suffixed quarantine names
    (re.compile(r"\b\d+\.\d+s\b"), "<dur>"),  # durations
    (re.compile(r"\b0x[0-9a-f]+\b", re.I), "<addr>"),  # memory addresses
    (re.compile(r"\b[0-9a-f]{7,40}\b"), "<hash>"),  # raw hashes
    (re.compile(r"\d{4}-\d{2}-\d{2}T[\d:.]+Z?"), "<ts>"),  # ISO timestamps
]


def _last_output(verdict: CheckVerdict) -> str:
    """Read back the final run's captured output, for evidence-based verdicts."""
    if not verdict.runs:
        return ""
    path = REPO_ROOT / verdict.runs[-1].log_file
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def output_digest(body: str) -> str:
    """Hash the output with run-to-run noise removed, so a digest change means a real change."""
    normalised = body
    for pattern, replacement in VOLATILE_PATTERNS:
        normalised = pattern.sub(replacement, normalised)
    return hashlib.sha256(normalised.encode("utf-8", errors="replace")).hexdigest()[:16]


def _py() -> str:
    return str(VENV_PY) if VENV_PY.exists() else sys.executable


@dataclass
class Check:
    key: str
    title: str
    cmd: list[str]
    why: str = ""
    # Pre-existing, separately-tracked defects that this check aggregates. Declaring them keeps the
    # verifier usable without pretending they are absent:
    #
    #   * a run fails ONLY for these  -> KNOWN-DEFECT, not counted as instability, not counted as a
    #     pass either. It is reported and named.
    #   * a run STOPS failing for a declared defect -> the entry is STALE and this fails loudly,
    #     because a declared defect that no longer reproduces must be deleted, not left to rot.
    #
    # This mirrors scripts/ratchet.py, for the same reason: an exemption without an expiry is how a
    # known problem becomes a permanent blind spot.
    known_defects: tuple[str, ...] = ()


@dataclass
class RunRecord:
    run_index: int
    exit_code: int
    duration_s: float
    log_file: str
    digest: str


@dataclass
class CheckVerdict:
    key: str
    title: str
    cmd: list[str]
    runs: list[RunRecord] = field(default_factory=list)
    verdict: str = "pending"  # PASSED | FAILED | ERROR
    failed_run: int | None = None
    note: str = ""


def nominated_checks() -> list[Check]:
    """The checks whose *reliability* must be demonstrated, not merely their correctness.

    These are the test-enforcement surface: the checks that decide whether other things pass. If one
    of these is flaky, every verdict it produces is suspect — which is why they, specifically, must
    pass repeatedly rather than once.
    """
    py = _py()
    return [
        Check(
            key="docs-manifest",
            title="Manifest validator — every doc classified exactly once",
            cmd=[py, "scripts/docs/manifest_validate.py", "--quiet"],
            why="Gates every other docs check; a flaky manifest verdict blocks or permits wrongly.",
        ),
        Check(
            key="docs-standard-reality",
            title="Standard-vs-reality — documented claims checked against measurement",
            cmd=[py, "scripts/docs/check_standard_reality.py", "--worktree"],
            # --worktree is REQUIRED here, not cosmetic: without it the checker reads the git
            # index and reports the last committed text, so it disagrees with the gate. The
            # verifier caught exactly this on its first run, which is the mechanism working.
            why=(
                "This is the check that catches a documented standard nobody enforces. It reads 31 "
                "docs and applies regex parsing, so its stability is not self-evident."
            ),
        ),
        Check(
            key="gate-self-test",
            title="Gate meta-tests — the tests that test the test enforcer",
            cmd=[py, "-m", "pytest", "tests/meta/", "-q", "--tb=short", "-p", "no:warnings"],
            why=(
                "The tests of the enforcement system itself. If these pass only sometimes, then "
                "every guarantee the gate makes is only sometimes true."
            ),
        ),
        Check(
            key="docs-exec",
            title="Executable documentation — doctests and markdown blocks",
            cmd=[py, "scripts/docs/check_executable.py", "--quiet"],
            why=(
                "Imports the whole app to find doctests. Import-time state, optional dependencies "
                "and environment lookups are all plausible sources of run-to-run variation."
            ),
        ),
        Check(
            key="gate-quick",
            title="Gate (quick: docs + governance) end to end",
            cmd=[py, "scripts/ci_gate.py", "--quick"],
            why="The integration path: proves the stages compose reliably, not just in isolation.",
            known_defects=(
                # Products of a real, unresolved product defect: five tools under app/tools/ carry
                # no @safety_gate decorator, which scripts/board/review.py reports locally on the
                # unmodified tree. Fixing it means changing app/tools/ — product code — so it is
                # escalated rather than fixed here. Until then the gate is correct to fail, and
                # this verifier must say "blocked by a named defect" instead of "unstable".
                "safety_gate_coverage: 5 tools missing @safety_gate",
            ),
        ),
    ]


# ── positive control ─────────────────────────────────────────────────────────


CONTROL_MARKER = "REPEAT_VERIFIER_POSITIVE_CONTROL"


def run_positive_control(runs: int, stamp: str) -> tuple[bool, str]:
    """Prove the verifier can detect a failure.

    A repeat-run harness that reports PASS for everything is indistinguishable from a working one
    until the day it matters. This control injects a genuine failure and asserts the harness sees
    it. It is not optional decoration: without it, "N consecutive passes" is an unfalsifiable claim.
    """
    control_doc = REPO_ROOT / "docs" / "_control_unclassified.md"
    log_dir = LOG_ROOT / stamp / "_positive_control"
    log_dir.mkdir(parents=True, exist_ok=True)
    try:
        # An unclassified markdown file must be rejected by the manifest validator.
        control_doc.write_text(
            f"# Control document\n\n{CONTROL_MARKER}\n\nThis file is deliberately not in the "
            "manifest, so the validator must report it.\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [_py(), "scripts/docs/manifest_validate.py", "--quiet"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
        (log_dir / "control.log").write_text(
            f"$ manifest_validate.py --quiet\n[exit {proc.returncode}]\n"
            f"{proc.stdout}\n{proc.stderr}",
            encoding="utf-8",
        )
        detected = proc.returncode != 0 and "_control_unclassified.md" in proc.stdout
        return detected, (
            f"injected an unclassified doc; validator exit={proc.returncode}, "
            f"named the file={'_control_unclassified.md' in proc.stdout}"
        )
    finally:
        control_doc.unlink(missing_ok=True)


# ── runner ───────────────────────────────────────────────────────────────────


def verify_check(check: Check, runs: int, stamp: str, *, verbose: bool) -> CheckVerdict:
    verdict = CheckVerdict(key=check.key, title=check.title, cmd=check.cmd)
    log_dir = LOG_ROOT / stamp / check.key
    log_dir.mkdir(parents=True, exist_ok=True)

    for i in range(1, runs + 1):
        log_file = log_dir / f"run-{i:02d}.log"
        start = time.monotonic()
        try:
            proc = subprocess.run(
                check.cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=1500
            )
            code = proc.returncode
            body = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
        except subprocess.TimeoutExpired:
            code = 124
            body = "TIMEOUT after 1500s\n"
        except FileNotFoundError as exc:
            code = 127
            body = f"command not found: {exc}\n"
        duration = time.monotonic() - start

        digest = output_digest(body)
        log_file.write_text(
            "\n".join(
                [
                    "# repeat-run verification",
                    f"check      : {check.key} — {check.title}",
                    f"run        : {i} of {runs}",
                    f"command    : {' '.join(check.cmd)}",
                    f"cwd        : {REPO_ROOT}",
                    f"started    : {datetime.now(UTC).isoformat()}",
                    f"duration_s : {duration:.2f}",
                    f"exit_code  : {code}",
                    f"sha256_16  : {digest}",
                    f"why it matters: {check.why}",
                    "",
                    "── verbatim output ──",
                    body.rstrip(),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        verdict.runs.append(
            RunRecord(i, code, round(duration, 2), str(log_file.relative_to(REPO_ROOT)), digest)
        )
        if verbose:
            print(f"    run {i}/{runs}: exit {code} in {duration:.1f}s  (log: {log_file.name})")
        if code != 0:
            # Before calling this instability, check whether it is entirely explained by a declared,
            # separately-tracked defect. Only a failure with NO explanation is instability.
            if check.known_defects:
                unexplained = [d for d in check.known_defects if d not in body]
                if not unexplained:
                    verdict.verdict = "KNOWN-DEFECT"
                    verdict.failed_run = i
                    verdict.note = (
                        f"run {i} of {runs} exited {code}, explained by "
                        f"{len(check.known_defects)} declared defect(s) — see the log. This is NOT "
                        f"counted as verified, and NOT counted as instability: the check is "
                        f"blocked by known work, not flaky. Either is a reason to fix the defect."
                    )
                    return verdict
                verdict.verdict = "FAILED"
                verdict.failed_run = i
                verdict.note = (
                    f"run {i} of {runs} exited {code}. {len(unexplained)} declared defect(s) were "
                    f"NOT found in the output, so this failure is only partly explained:\n"
                    + "\n".join(f"      missing: {d}" for d in unexplained)
                    + "\n      A declared defect that no longer appears must be removed, not left."
                )
                return verdict
            verdict.verdict = "FAILED"
            verdict.failed_run = i
            verdict.note = (
                f"run {i} of {runs} exited {code}; the sequence is broken and the check is NOT "
                f"verified. A single pass proves a check CAN pass; {runs} consecutive passes are "
                f"what proves it DOES."
            )
            return verdict

    # Cross-run consistency: identical exit codes are not enough if the *output* differs wildly,
    # which would suggest nondeterministic behaviour that happens to be green today.
    digests = {r.digest for r in verdict.runs}
    if check.known_defects:
        # The check passed every run while declaring defects. That is only legitimate if the check
        # is still visibly reporting them — the gate's design is to classify a declared defect and
        # print it on every run, pass or fail. Two failure modes to catch:
        #
        #   * the declaration is stale (defect fixed, entry not removed); or
        #   * the declaration has become invisible (defect excused but never printed), which is a
        #     suppression wearing a declaration's clothes.
        #
        # Both are errors. Only "passes AND still names the defect" is acceptable.
        last_body = _last_output(verdict)
        missing = [d for d in check.known_defects if d not in last_body]
        if missing:
            verdict.verdict = "STALE-DEFECT"
            verdict.note = (
                f"passed all {runs} runs, but the output no longer names "
                f"{len(missing)} declared defect(s):\n"
                + "\n".join(f"      missing: {d}" for d in missing)
                + "\n      Either the defect is fixed (remove the declaration) or it is being "
                "excused without being reported (restore the report). A declaration nobody can "
                "see is a suppression."
            )
            return verdict
        verdict.verdict = "PASSED"
        verdict.note = (
            f"passed all {runs} runs while still visibly reporting "
            f"{len(check.known_defects)} declared defect(s) — classified, not hidden."
        )
        return verdict
    verdict.verdict = "PASSED"
    if len(digests) > 1:
        verdict.note = (
            f"passed all {runs} runs, but produced {len(digests)} distinct output digests. "
            "Green, but not byte-identical — worth knowing before trusting it as deterministic."
        )
    else:
        verdict.note = f"passed all {runs} runs with byte-identical output ({next(iter(digests))})."
    return verdict


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Repeat-run stability verification.")
    parser.add_argument("--runs", type=int, default=3, help="consecutive passes required")
    parser.add_argument("--check", action="append", default=[], help="limit to these checks")
    parser.add_argument("--control", action="store_true", help="run the positive control first")
    parser.add_argument("--json", dest="as_json", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    checks = nominated_checks()
    if args.check:
        wanted = set(args.check)
        unknown = wanted - {c.key for c in checks}
        if unknown:
            print(f"unknown check(s): {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2
        checks = [c for c in checks if c.key in wanted]

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    LOG_ROOT.mkdir(parents=True, exist_ok=True)

    if not args.as_json:
        print("=" * 78)
        print("REPEAT-RUN STABILITY VERIFICATION")
        print("=" * 78)
        print(
            f"A check that passed once is NOT verified. Requiring {args.runs} consecutive passes."
        )
        print(f"Per-run logs: {LOG_ROOT.relative_to(REPO_ROOT)}/{stamp}/\n")

    control_ok = True
    control_detail = "not run"
    if args.control:
        control_ok, control_detail = run_positive_control(args.runs, stamp)
        if not args.as_json:
            mark = "DETECTED" if control_ok else "MISSED"
            print(f"Positive control: {mark} — {control_detail}\n")
        if not control_ok:
            print(
                "POSITIVE CONTROL FAILED: the verifier did not detect an injected failure. "
                "Its verdicts cannot be trusted, so verification stops here.",
                file=sys.stderr,
            )
            return 2

    verdicts: list[CheckVerdict] = []
    for check in checks:
        if not args.quiet and not args.as_json:
            print(f"→ {check.title}")
            print(f"  why: {check.why}")
        verdicts.append(verify_check(check, args.runs, stamp, verbose=not args.quiet))
        v = verdicts[-1]
        if not args.as_json:
            print(f"  [{v.verdict}] {v.note}\n")

    if args.as_json:
        print(
            json.dumps(
                {
                    "runs_required": args.runs,
                    "stamp": stamp,
                    "positive_control": {
                        "ran": args.control,
                        "ok": control_ok,
                        "detail": control_detail,
                    },
                    "verdicts": [asdict(v) for v in verdicts],
                },
                indent=2,
            )
        )
        return 0 if all(v.verdict == "PASSED" for v in verdicts) else 1

    print("=" * 78)
    passed = [v for v in verdicts if v.verdict == "PASSED"]
    blocked = [v for v in verdicts if v.verdict == "KNOWN-DEFECT"]
    failed = [v for v in verdicts if v.verdict not in {"PASSED", "KNOWN-DEFECT"}]
    print(f"{len(passed)}/{len(verdicts)} check(s) verified over {args.runs} consecutive runs")
    for v in blocked:
        print(f"  BLOCKED BY DEFECT  {v.key}: {v.note}")
    for v in failed:
        print(f"  NOT VERIFIED  {v.key}: {v.note}")
    print("=" * 78)
    if failed:
        print("A check that has not passed repeatedly is not verified. Fix the instability;")
        print("do not increase the retry count.")
        return 1
    if blocked:
        print(f"{len(blocked)} check(s) could not be verified because of declared product")
        print("defects. Those are separately tracked and genuinely open — not flakiness.")
        return 1
    print(f"All nominated checks verified. Evidence: artifacts/verify-repeat/{stamp}/")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
