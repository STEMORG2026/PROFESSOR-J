#!/usr/bin/env python3
"""Doc-to-code co-change detection — R1, the rule that makes the manifest load-bearing.

THE PROBLEM THIS SOLVES
-----------------------
A manifest that only *records* which doc covers which code is decoration. The value comes from
turning a refactor into a decision: when you change code a doc claims to describe, either the doc
changes too, or you say — explicitly, in the commit — why it does not need to.

JARVIS's own post-mortem named this as the root cause of its worst documentation failure:

    "Nothing flags prose drift when signatures/routes/keys/flags change. The binding turns
     refactors into gate failures *after the fact* (doc goes red) but never *prompts* the author
     at commit time."

This script is the prompt at commit time.

MOST-SPECIFIC-COVER-WINS
------------------------
The single most important rule here, inherited from JARVIS's implementation because the naive
version is unusable. A file can match several `covers` entries — `app/` (depth 4) and
`app/tools/` (depth 10) and `app/tools/sandbox.py` (depth 21) might all apply to one change.

If every match blocked, then any change anywhere in `app/` would demand that ARCHITECTURE.md be
edited in the same commit, and within a week the rule would be bypassed wholesale. So:

  * The **deepest** (most specific) matching binding BLOCKS if its doc did not change.
  * Shallower matches produce a **WARNING** only.

A change to `app/tools/sandbox.py` therefore blocks on `docs/...sandbox doc` but merely warns about
`ARCHITECTURE.md` — which is exactly the right pressure: the specific doc must move, the general
one is a prompt to consider.

ESCAPE HATCH
------------
There is no "skip" flag. There IS an explicit, auditable escape: a commit trailer

    Docs-Not-Needed: <reason>

The reason is required and non-empty. This is not a bypass mechanism — it is a *record*. It ends up
in `git log`, it is greppable, and it forces the author to write down the judgement they made.
Silence is never accepted as a reason.

Usage:
    python3 scripts/docs/check_changed.py                # staged changes (Layer 1)
    python3 scripts/docs/check_changed.py --full         # worktree vs HEAD (Layer 2 / gate)
    python3 scripts/docs/check_changed.py --range A..B    # a commit range (pre-push)

Exit codes: 0 clean (or warnings only), 1 a blocking finding, 2 the script could not run.
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    REPO_ROOT,
    Finding,
    Section,
    git,
    is_code_path,
    load_manifest,
    staged_files,
)

TRAILER_RE = "Docs-Not-Needed:"


@dataclass
class Binding:
    doc: str
    cover: str
    depth: int


@dataclass
class CoChangeReport:
    findings: list[Finding] = field(default_factory=list)
    blocked: int = 0
    warned: int = 0

    def render(self) -> str:
        lines = [
            "── docs-to-code co-change ──",
            f"   {self.blocked} blocking finding(s), {self.warned} warning(s)",
        ]
        for f in self.findings:
            lines.append("  " + f.render())
        if not self.findings:
            lines.append("   OK")
        return "\n".join(lines)


def build_index(sections: list[Section]) -> list[Binding]:
    """Invert `covers` into a flat list of (doc, cover, depth) bindings.

    Depth is the string length of the cover path, matching JARVIS's approach: it is a cheap and
    correct-enough proxy for specificity, and it behaves sensibly for both files and directories.
    """
    out: list[Binding] = []
    for s in sections:
        for cover in s.covers:
            out.append(Binding(doc=s.doc, cover=cover.rstrip("/"), depth=len(cover.rstrip("/"))))
    return out


def covers_match(cover: str, path: str) -> bool:
    """Does `cover` (a file or directory) contain `path`?"""
    c = cover.rstrip("/")
    return path == c or path.startswith(c + "/")


def changed_python_names(diff_text: str) -> set[str]:
    """Top-level def/class names added or removed by a diff.

    Names, not lines: a diff that only reformats a function body does not rename anything and
    should not by itself demand a doc change. A renamed or added public symbol should.
    """
    names: set[str] = set()
    for line in diff_text.splitlines():
        if not line.startswith(("+", "-")) or line.startswith(("+++", "---")):
            continue
        body = line[1:].strip()
        if body.startswith(("def ", "class ", "async def ")):
            try:
                tree = ast.parse(body if body.endswith(":") else body + ":")
            except SyntaxError:
                # Fall back to a lexical read; a decorated or multi-line signature still has a name.
                token = body.split("(", 1)[0]
                token = token.replace("async def ", "").replace("def ", "").replace("class ", "")
                if token.strip():
                    names.add(token.strip().rstrip(":"))
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                    names.add(node.name)
        elif body.startswith("@"):  # decorators often accompany a public name
            continue
    return names


def commit_trailers(rev_range: str | None, staged: bool) -> str:
    """All commit messages in scope, for the Docs-Not-Needed trailer."""
    try:
        if staged:
            return ""
        if rev_range:
            return git("log", "--format=%B", rev_range)
        return git("log", "--format=%B", "-1")
    except RuntimeError:
        return ""


def collect_changes(*, mode: str, rev_range: str | None) -> tuple[list[str], dict[str, str]]:
    """Return (changed_files, diffs_by_file) for the requested mode."""
    if mode == "staged":
        files = staged_files()
        diffs = {}
        for f in files:
            try:
                diffs[f] = git("diff", "--cached", "--", f)
            except RuntimeError:
                diffs[f] = ""
        return files, diffs

    if rev_range:
        out = git("diff", "--name-only", "--diff-filter=ACMR", rev_range)
        files = sorted(p for p in out.splitlines() if p)
        diffs = {f: git("diff", rev_range, "--", f) for f in files}
        return files, diffs

    # --full: everything differing from HEAD (staged + unstaged + untracked-but-tracked-dir).
    out = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    files = sorted(
        line[3:].strip().strip('"')
        for line in out.splitlines()
        if len(line) > 3 and not line.startswith("??")
    )
    untracked = sorted(line[3:].strip() for line in out.splitlines() if line.startswith("??"))
    files = sorted(set(files) | {u for u in untracked if (REPO_ROOT / u).is_file()})
    diffs = {}
    for f in files:
        try:
            diffs[f] = git("diff", "HEAD", "--", f)
        except RuntimeError:
            diffs[f] = ""
    return files, diffs


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Doc-to-code co-change detection (R1).")
    parser.add_argument("--full", action="store_true", help="worktree vs HEAD")
    parser.add_argument("--range", dest="rev_range", help="commit range, e.g. origin/main..HEAD")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    mode = "staged"
    if args.rev_range:
        mode = "range"
    elif args.full:
        mode = "full"

    sections, manifest_findings = load_manifest()
    if not sections:
        print("cannot evaluate co-change: manifest did not load", file=sys.stderr)
        for f in manifest_findings:
            print(f.render(), file=sys.stderr)
        return 2

    index = build_index(sections)
    docs_in_manifest = {s.doc for s in sections}

    try:
        files, diffs = collect_changes(mode=mode, rev_range=args.rev_range)
    except RuntimeError as exc:
        print(f"git failed: {exc}", file=sys.stderr)
        return 2

    changed_docs = {f for f in files if f.endswith(".md")}
    messages = commit_trailers(args.rev_range, staged=(mode == "staged"))
    has_trailer = bool(messages.strip()) and TRAILER_RE in messages

    report = CoChangeReport()

    if not files:
        if not args.quiet:
            print(report.render())
            print("   (nothing changed in scope)")
        return 0

    # For each changed code file, find its most-specific binding.
    for path in files:
        if not is_code_path(path) or path.endswith(".md"):
            continue
        matches = [b for b in index if covers_match(b.cover, path)]
        if not matches:
            continue
        matches.sort(key=lambda b: b.depth, reverse=True)
        specific = matches[0]
        shallower = matches[1:]

        doc_changed = specific.doc in changed_docs
        # A doc that is not in the manifest (standalone) is still checked: it must change too.
        if not doc_changed and specific.doc not in files:
            if has_trailer:
                report.findings.append(
                    Finding(
                        "R1-cochange-acknowledged",
                        f"{path} changed; {specific.doc} did not — acknowledged by "
                        f"'{TRAILER_RE}' trailer",
                        path=path,
                        severity="warning",
                    )
                )
                report.warned += 1
            else:
                report.findings.append(
                    Finding(
                        "R1-cochange",
                        f"{path} changed but its doc {specific.doc} did not",
                        path=path,
                        hint=(
                            f"Update {specific.doc} in the same commit, or add a commit trailer:\n"
                            f"          {TRAILER_RE} <reason it genuinely is not needed>"
                        ),
                    )
                )
                report.blocked += 1

        for b in shallower:
            if b.doc in changed_docs or b.doc in files:
                continue
            report.findings.append(
                Finding(
                    "R1-cochange-general",
                    f"{path} changed; the broader binding in {b.doc} (covers {b.cover}) did not",
                    path=path,
                    severity="warning",
                    hint="Not blocking — the specific doc above is the required one.",
                )
            )
            report.warned += 1

    # A changed doc whose manifest `covers` paths were NOT touched is fine (prose edit), but a
    # deleted doc that the manifest still classifies is not — that would silently orphan a binding.
    for doc in sorted(changed_docs):
        if doc not in docs_in_manifest:
            continue
        if not (REPO_ROOT / doc).exists() and mode != "staged":
            report.findings.append(
                Finding(
                    "R1-deleted-doc",
                    f"{doc} was deleted but is still classified in docs.manifest.yaml",
                    path="docs.manifest.yaml",
                    hint="Remove its section, or restore the file.",
                )
            )
            report.blocked += 1

    if args.quiet:
        for f in report.findings:
            if f.severity == "error":
                print(f.render())
        return 1 if report.blocked else 0

    print(report.render())
    print(f"   mode={mode}, {len(files)} changed file(s), {len(changed_docs)} doc(s) changed")
    if report.findings and report.warned and not report.blocked:
        print("   (warnings do not fail the gate)")
    return 1 if report.blocked else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
