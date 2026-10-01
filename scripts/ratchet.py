#!/usr/bin/env python3
"""Baseline ratchet — pass if you do not make things worse, fail if you do.

THE PROBLEM
-----------
A gate that fails on every pre-existing violation is a gate nobody can satisfy, so it gets bypassed
or ignored — which is exactly how this repository ended up with thirty consecutive red CI runs that
nobody read. But simply exempting the offending files is worse: it converts a known problem into a
permanent blind spot and guarantees it never gets fixed.

THE RATCHET
-----------
A known-violation baseline is recorded in a file. The gate then applies three rules:

  1. A violation **not** in the baseline FAILS. You cannot introduce new non-conformance.
  2. A violation **in** the baseline is reported, not failed. Existing debt is visible.
  3. A baseline entry that is **no longer violated** FAILS the ratchet as *stale*, forcing the
     entry to be deleted.

Rule 3 is what makes this a ratchet rather than a permanent exemption, and it is the rule most
implementations omit. Without it, the baseline only ever grows: someone fixes a file, forgets to
remove the entry, and the exemption silently outlives the problem. With it, the baseline can only
shrink, and the count is a real measure of remaining debt.

Usage:
    python3 scripts/ratchet.py format            # check the format ratchet
    python3 scripts/ratchet.py format --update   # re-record the baseline (requires review)

Exit codes: 0 no new violations and no stale entries, 1 otherwise, 2 could not run.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_DIR = REPO_ROOT / ".gate-baseline"
VENV_PY = REPO_ROOT / ".venv" / "bin" / "python"


def _py() -> str:
    return str(VENV_PY) if VENV_PY.exists() else sys.executable


# Ratchets we track. Each is a command whose stdout lists offending files, plus the paths to check.
RATCHETS: dict[str, dict[str, object]] = {
    "lint": {
        "command": [_py(), "-m", "ruff", "check", "--output-format", "concise"],
        "paths": ["app/", "tests/", "scripts/"],
        "extra_args": ["--extend-exclude", "*.sh"],
        "marker": ": ",
        "why": (
            "Pre-existing ruff findings, concentrated in app/skills/builtin.py (unsorted imports "
            "and blank-line whitespace) plus two unused imports in app/routers/. Fixing "
            "builtin.py's findings is entangled with reformatting 339 lines of it, which is too "
            "large to fold into a tooling change. The ratchet keeps them visible and blocks new "
            "ones; the list can only shrink."
        ),
    },
    "format": {
        "command": [_py(), "-m", "ruff", "format", "--check"],
        "paths": ["app/", "tests/", "scripts/"],
        "extra_args": ["--exclude", "*.sh"],
        "marker": "Would reformat: ",
        "path_after_marker": True,
        "why": (
            "Files that `ruff format --check` reports. The baseline exists because reformatting "
            "app/skills/builtin.py alone rewrites 339 lines of semantically-neutral code — too "
            "large a diff to smuggle into a tooling change, and not something to do without review."
        ),
    },
}


def offending_files(spec: dict[str, object]) -> list[str] | None:
    """Return the list of files the ratchet's command objects to, or None if it could not run."""
    cmd = [*spec["command"], *spec["paths"], *spec["extra_args"]]  # type: ignore[misc]
    try:
        proc = subprocess.run(
            cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=600, check=False
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    # A tool that failed to run must not be read as "found nothing". `ruff check` exits 1 when it
    # finds violations, and `ruff format --check` exits 1 when files would be reformatted, so 0 and
    # 1 both mean "ran fine". Anything else is a tool error — a bad flag, a missing path, a crash —
    # and must fail loudly rather than yield an empty (and therefore passing) violation list.
    if proc.returncode not in (0, 1):
        return None

    marker = str(spec["marker"])
    # WHERE THE PATH SITS RELATIVE TO THE MARKER IS TOOL-SPECIFIC, and getting it wrong is silent:
    # the parser simply yields no filenames, the ratchet reports zero violations, and the stage
    # passes while inspecting nothing. That happened — the `format` ratchet read as clean for as
    # long as it existed, because this function assumed every tool printed the path first.
    #
    #   ruff check  --output-format concise :  path/to/f.py:12:5: F401 ...   (path BEFORE)
    #   ruff format --check                 :  Would reformat: path/to/f.py  (path AFTER)
    #
    # So each ratchet declares which it is, rather than the runner guessing.
    path_after_marker = bool(spec.get("path_after_marker", False))
    found: set[str] = set()
    for line in (proc.stdout + proc.stderr).splitlines():
        if marker not in line:
            continue
        if path_after_marker:
            candidate = line.split(marker, 1)[1].strip()
        else:
            head = line.split(marker, 1)[0]
            parts = head.split(":")
            # A path may itself contain ":", so the split is validated rather than assumed: only
            # treat parts[0] as the path when parts[1] really is a line number.
            has_line_number = len(parts) >= 2 and parts[1].isdigit()
            candidate = (parts[0] if has_line_number else head).strip()
        if candidate and not candidate.startswith(("Found", "error", "warning", "Usage", "#")):
            found.add(candidate)
    return sorted(found)


def baseline_path(name: str) -> Path:
    return BASELINE_DIR / f"{name}.json"


def load_baseline(name: str) -> list[str]:
    path = baseline_path(name)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return sorted(data.get("files", []))


def save_baseline(name: str, files: list[str], why: str) -> None:
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    baseline_path(name).write_text(
        json.dumps(
            {
                "_comment": (
                    "Known pre-existing violations. The gate FAILS on any file NOT listed here "
                    "(no new debt) and ALSO fails if a listed file stops violating (stale entry), "
                    "so this list can only shrink. Regenerate with scripts/ratchet.py "
                    f"{name} --update — and review the diff before committing it."
                ),
                "_why": why,
                "files": sorted(files),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def check(name: str, *, update: bool, quiet: bool) -> int:
    spec = RATCHETS.get(name)
    if spec is None:
        print(f"unknown ratchet: {name}", file=sys.stderr)
        return 2

    current = offending_files(spec)
    if current is None:
        print(f"ratchet {name}: could not run the underlying command", file=sys.stderr)
        return 2

    if update:
        save_baseline(name, current, str(spec["why"]))
        print(f"ratchet {name}: baseline recorded with {len(current)} file(s)")
        for f in current:
            print(f"  (known) {f}")
        return 0

    baseline = load_baseline(name)
    new = sorted(set(current) - set(baseline))
    fixed = sorted(set(baseline) - set(current))

    if not quiet:
        print(f"── ratchet: {name} ──")
        print(f"   {len(current)} current violation(s), {len(baseline)} in baseline")
        for f in current:
            tag = "(known)" if f in baseline else "NEW    "
            print(f"   {tag} {f}")

    exit_code = 0
    if new:
        print()
        print(f"  FAIL: {len(new)} NEW violation(s) not in the baseline:")
        for f in new:
            print(f"    + {f}")
        print("  You cannot add non-conformance. Fix these, or justify them in review.")
        exit_code = 1
    if fixed:
        print()
        print(
            f"  FAIL: {len(fixed)} baseline entr(y/ies) no longer violate — the baseline is stale:"
        )
        for f in fixed:
            print(f"    - {f}")
        print("  Good news: those are fixed. Remove them so the ratchet can tighten:")
        print(f"    python3 scripts/ratchet.py {name} --update")
        exit_code = 1
    if exit_code == 0:
        print(f"  OK: no new violations, no stale entries ({len(current)} known remaining)")
    return exit_code


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Baseline ratchet.")
    parser.add_argument("name", nargs="?", default="format", help="ratchet to check")
    parser.add_argument(
        "--update", action="store_true", help="record the current state as baseline"
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    return check(args.name, update=args.update, quiet=args.quiet)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
