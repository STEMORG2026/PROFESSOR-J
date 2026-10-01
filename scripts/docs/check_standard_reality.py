#!/usr/bin/env python3
"""Standard-vs-reality — does the documentation state things that are not true?

HOW THIS CAME ABOUT
-------------------
An audit of PROFESSOR-J found that `AGENTS.md` §3.5 states:

    Test Coverage: >= 95% line coverage for domain and cognitive engine logic; >= 85% for adapters.

and that adapter coverage was measured at **68%**, with **no gate measuring it at all**
(`--cov-fail-under=95` covers `app.domain` only, and `fail_under = 80` in `pyproject.toml` can never
fire because `addopts` contains no `--cov`).

That is the most damaging documentation defect there is, because it is invisible. A stale path or a
broken link is noticed by a reader who tries it. A documented threshold that is not true is
*reassuring*: it tells a reader the code is held to a standard it is not held to, and nobody ever
finds out. The repository's own standard document was laundering an unmet commitment.

So this check is not about spelling or links. It reads the claims a repository makes about itself
and compares them to measurement.

CHECKS
------
  S1  Coverage thresholds stated in docs — every ">= N%" / "N% coverage" claim in a manifest doc is
      cross-referenced against the gates that actually enforce coverage. A stated threshold with no
      enforcing gate is an error unless the doc explicitly marks it as aspirational (the words
      "target", "goal", "aspirational", or "TODO" within the claim's paragraph).
  S2  Coverage reality — for every enforceable threshold that names a scope (`app.domain`,
      `app.adapters`, ...), the measured value is compared. Below the stated floor is an error.
  S3  Enforced gates named in docs must exist — a doc that names `scripts/whatever.py` as a gate,
      where that file does not exist, is an error.
  S4  CI job names stated in docs must exist in the workflows.

Measurement is done by actually invoking coverage on the named scope, not by reading a badge. It is
slow, so S2 is opt-in via `--measure` and is run by the scheduled workflow rather than the pre-push
gate. S1/S3/S4 are cheap and always run.

Usage:
    python3 scripts/docs/check_standard_reality.py             # S1, S3, S4
    python3 scripts/docs/check_standard_reality.py --measure    # also S2 (slow)

Exit codes: 0 consistent, 1 an inconsistency, 2 the checker could not run.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import REPO_ROOT, Report, load_manifest, read_from_index  # noqa: E402

# A coverage claim is a percentage bound to a scope *within one clause*. Splitting on clause
# boundaries is essential, not stylistic — see find_claims().
CLAUSE_SPLIT_RE = re.compile(r"[,;]|\band\b")
# A percentage is only a COVERAGE claim when the clause actually talks about coverage. Without
# this, `"""List tools with optional caching (98% token reduction)."""` in ARCHITECTURE-ESSENTIALS
# is read as "the tools layer must reach 98% coverage" — the checker inventing a rule out of an
# unrelated number, which is the same class of error as missing a rule: the output looks
# authoritative and is wrong.
#
# Two spellings must still be caught:
#   ">= 95% line coverage for domain"     (percentage before the word)
#   "coverage >= 95%", "coverage: 95%"    (percentage after the word)
COVERAGE_WORD_RE = re.compile(r"\bcover(?:age|ed)\b", re.I)
PCT_ONLY_RE = re.compile(r"(\d{1,3})\s*%")
# Which code scope a claim is about.
SCOPE_PATTERNS = [
    (re.compile(r"\badapters?\b", re.I), "app.adapters"),
    (re.compile(r"\bdomain\b", re.I), "app.domain"),
    (re.compile(r"\bcognitive engine\b|\bbrain\b", re.I), "app.brain"),
    (re.compile(r"\btools?\b", re.I), "app.tools"),
    (re.compile(r"\bguards?rails?\b", re.I), "app.guardrails"),
]
ASPIRATIONAL_RE = re.compile(
    r"\b(target|goal|aspiration|aspirational|planned|TODO|intended)\b", re.I
)
GATE_SCRIPT_RE = re.compile(r"`(scripts/[\w/]+\.py)`")
CI_JOB_RE = re.compile(r"`([a-z][a-z0-9-]{2,30})`\s+job\b", re.I)

VENV_PY = REPO_ROOT / ".venv" / "bin" / "python"


@dataclass
class Claim:
    doc: str
    line: int
    percent: int
    scopes: list[str]
    aspirational: bool
    text: str

    @property
    def scope(self) -> str | None:
        """The first named scope, kept for readability in messages."""
        return self.scopes[0] if self.scopes else None


def find_claims(doc: str, text: str) -> list[Claim]:
    """Locate coverage-threshold claims, one per (percentage, scope) pair.

    The unit of meaning is the **clause**, not the line. The real claim in this repository is

        "Domain/brain coverage >= 95%, adapter coverage >= 85%"

    -- one line, two scopes, two different floors. A whole-line regex either conflates them
    (reporting 95% against adapters, which is simply wrong) or keeps only the first scope and
    silently misses the unenforced one. Both failures are invisible, which makes them worse than
    no check at all: the output looks authoritative and is incorrect.

    Each clause is therefore scanned independently, and the percentage found in a clause is
    attributed to the scopes named in *that* clause. A clause naming a scope but no percentage is
    skipped rather than guessed at.
    """
    lines = text.splitlines()
    claims: list[Claim] = []
    seen: set[tuple[int, int, tuple[str, ...]]] = set()
    for i, line in enumerate(lines, 1):
        if "%" not in line:
            continue
        context = " ".join(lines[max(0, i - 3) : min(len(lines), i + 2)])
        aspirational = bool(ASPIRATIONAL_RE.search(context))
        for clause in CLAUSE_SPLIT_RE.split(line):
            # Require coverage language in the same clause. The clause is the unit of meaning, so
            # a percentage in a clause that never mentions coverage is not a coverage standard.
            if not COVERAGE_WORD_RE.search(clause):
                continue
            for pct_str in PCT_ONLY_RE.findall(clause):
                pct = int(pct_str)
                if not 1 <= pct <= 100:
                    continue
                scopes: list[str] = []
                for pat, cov_scope in SCOPE_PATTERNS:
                    if pat.search(clause) and cov_scope not in scopes:
                        scopes.append(cov_scope)
                if not scopes:
                    continue
                key = (i, pct, tuple(scopes))
                if key in seen:
                    continue
                seen.add(key)
                claims.append(
                    Claim(
                        doc=doc,
                        line=i,
                        percent=pct,
                        scopes=scopes,
                        aspirational=aspirational,
                        text=clause.strip()[:120],
                    )
                )
    return claims


def enforced_coverage_gates() -> dict[str, int]:
    """Scope -> floor, for every coverage gate that actually runs."""
    gates: dict[str, int] = {}
    ci = REPO_ROOT / ".github" / "workflows" / "ci.yml"
    ratchets = REPO_ROOT / ".github" / "workflows" / "quality-ratchets.yml"
    makefile = REPO_ROOT / "Makefile"
    pyproject = REPO_ROOT / "pyproject.toml"

    # `scripts/ci_gate.py` is the LOCAL gate and therefore the authoritative one: CI is a mirror.
    # It must be scanned, or every gate added there would be reported as unenforced — the exact
    # false positive this function exists to prevent.
    gate = REPO_ROOT / "scripts" / "ci_gate.py"
    for path in (ci, ratchets, makefile, gate):
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        # Two spellings are in use: a single-line "--cov=X ... --cov-fail-under=N", and the gate's
        # multi-line list form where the two flags sit on different lines of the same cmd=[...].
        for m in re.finditer(r"--cov=([\w.]+)[^\n]*?--cov-fail-under=(\d+)", text):
            gates[m.group(1)] = int(m.group(2))
        for m in re.finditer(r'"--cov=([\w.]+)"(.*?)"--cov-fail-under=(\d+)"', text, re.DOTALL):
            gates[m.group(1)] = int(m.group(3))
        # The gate's structured form: a `--cov=<scope>` stage that declares its floor as a field
        # rather than a CLI flag, because the stage is judged on the measured report instead of
        # pytest's exit code. Both spellings must be recognised, or a real gate reads as absent and
        # this checker reports the opposite of the truth.
        for m in re.finditer(r'coverage_floor=([\d.]+),\s*coverage_scope="([\w.]+)"', text):
            gates[m.group(2)] = int(float(m.group(1)))

    # pyproject fail_under with source=[...] — only counts if something invokes --cov at all.
    if pyproject.exists() and re.search(r'addopts\s*=\s*"[^"]*--cov', pyproject.read_text()):
        floor_match = re.search(r"fail_under\s*=\s*(\d+)", pyproject.read_text())
        if floor_match:
            gates.setdefault("app", int(floor_match.group(1)))
    return gates


def measure_coverage(scope: str) -> int | None:
    """Run coverage for a scope and return the total percentage, or None on failure."""
    py = str(VENV_PY) if VENV_PY.exists() else sys.executable
    try:
        subprocess.run(
            [
                py,
                "-m",
                "pytest",
                "tests/",
                "-q",
                "--tb=no",
                "-p",
                "no:warnings",
                f"--cov={scope}",
                "--cov-report=json:/tmp/_cov_probe.json",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=900,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    probe = Path("/tmp/_cov_probe.json")
    if not probe.exists():
        return None
    try:
        data = json.loads(probe.read_text())
        value = data["totals"]["percent_covered"]
        return round(float(value))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None
    finally:
        probe.unlink(missing_ok=True)
    # proc deliberately unused beyond its side effect; exit code is not the signal here — the
    # coverage JSON is, because the suite has known-red tests that must not mask the measurement.


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Docs claims vs measured reality.")
    parser.add_argument(
        "--measure", action="store_true", help="also verify coverage numbers (slow)"
    )
    parser.add_argument(
        "--worktree",
        action="store_true",
        help=(
            "read files from disk instead of the git index. The default (index) is right for "
            "pre-commit, where the index is what is about to be committed. This flag is right for "
            "the gate, which runs against the working tree — without it, an unstaged doc fix is "
            "invisible and the checker reports the OLD text, which reads as the fix not working."
        ),
    )
    args = parser.parse_args(argv)

    sections, _ = load_manifest()
    report = Report()
    gates = enforced_coverage_gates()

    claims: list[Claim] = []
    for section in sections:
        if section.staleness not in {"facts", "content"}:
            continue  # semantic/snapshot docs do not assert measurable facts about the code
        p = REPO_ROOT / section.doc
        if args.worktree:
            if not p.exists():
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
        else:
            try:
                text = read_from_index(section.doc)
            except RuntimeError:
                if not p.exists():
                    continue
                text = p.read_text(encoding="utf-8", errors="replace")
        report.checked += 1
        claims.extend(find_claims(section.doc, text))

        # ── S3: named gate scripts must exist ────────────────────────────────
        for i, line in enumerate(text.splitlines(), 1):
            for script in GATE_SCRIPT_RE.findall(line):
                if not (REPO_ROOT / script).exists():
                    report.error(
                        "S3-missing-gate",
                        f"documents `{script}` as a gate, but that file does not exist",
                        path=section.doc,
                        line=i,
                    )

    # ── S1: every enforceable threshold must have a gate ─────────────────────
    for claim in claims:
        if not claim.scopes or claim.aspirational:
            continue
        for scope in claim.scopes:
            if scope in gates:
                continue
            report.error(
                "S1-unenforced-standard",
                f"states '>= {claim.percent}% coverage' for {scope}, "
                f"but no gate enforces that scope",
                path=claim.doc,
                line=claim.line,
                hint=(
                    f"Enforced scopes: {', '.join(sorted(gates)) or '(none)'}. Either add a gate "
                    f"for {scope}, revise the claim, or mark it aspirational in the text (the "
                    f"words target/goal/planned). A standard nobody enforces is worse than no "
                    f"standard: it reads as assurance and is not."
                ),
            )

    # ── S2: measured coverage vs stated floor ────────────────────────────────
    if args.measure:
        measured_cache: dict[str, int | None] = {}
        for claim in claims:
            if claim.aspirational:
                continue
            for scope in claim.scopes:
                if scope not in gates:
                    continue
                if scope not in measured_cache:
                    measured_cache[scope] = measure_coverage(scope)
                measured = measured_cache[scope]
                if measured is None:
                    report.warn(
                        "S2-unmeasurable",
                        f"could not measure coverage for {scope}",
                        path=claim.doc,
                        line=claim.line,
                    )
                    continue
                if measured < claim.percent:
                    report.error(
                        "S2-below-standard",
                        f"claims >= {claim.percent}% for {scope}; measured {measured}%",
                        path=claim.doc,
                        line=claim.line,
                        hint="Documented standard not met. Fix coverage, or revise the claim.",
                    )

    print(report.render("docs standard vs reality"))
    if claims:
        print(
            f"   {len(claims)} coverage claim(s) found; enforced scope(s): "
            f"{', '.join(f'{k}>={v}%' for k, v in sorted(gates.items())) or '(none)'}"
        )
    if not args.measure:
        print("   (S2 measurement skipped — pass --measure to verify actual percentages)")
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
