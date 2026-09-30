#!/usr/bin/env python3
"""Documentation structure and integrity checks.

Covers the things a reader notices immediately and a linter can prove:

  D1  Heading structure      — exactly one H1 per doc, no skipped heading levels.
  D2  Fenced code blocks     — every fence is closed, and non-empty.
  D3  Internal links         — every relative [text](target) resolves, and anchors that point
                               into another file name a heading that exists.
  D4  Backticked paths       — a `path/like/this.py` that does not exist is a stale reference.
  D5  Freshness header       — every manifest doc declares Status/Last Updated, so staleness is
                               visible to a reader rather than only to a tool.
  D6  Drift markers          — TODO/FIXME/XXX counts are reported; a doc that is mostly TODO is
                               not documentation.
  D7  Placeholder detection  — unreplaced <angle-bracket> placeholders and lorem ipsum.
  D8  Line length / trailing whitespace on changed docs.

D3 is deliberately strict about *anchors into other files* because that is the check that catches
a real class of decay: a section gets renamed, inbound links keep "working" (the file exists) while
landing the reader nowhere.

Usage:
    python3 scripts/docs/check_docs.py [paths...]     # default: all tracked markdown
    python3 scripts/docs/check_docs.py --quiet

Exit codes: 0 clean (warnings allowed), 1 errors found, 2 config problem.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    REPO_ROOT,
    Report,
    load_manifest,
    read_from_index,
    standalone_reason,
    tracked_markdown,
)

FENCE_RE = re.compile(r"^(\s*)(`{3,}|~{3,})\s*(\S*)\s*$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
BACKTICK_PATH_RE = re.compile(
    r"`([A-Za-z0-9_./-]+\.(?:py|md|yaml|yml|toml|json|ts|tsx|js|cfg|txt))`"
)
HTML_ANCHOR_RE = re.compile(r"<a\s+[^>]*id=[\"']([^\"']+)[\"']", re.I)
PLACEHOLDER_RE = re.compile(r"<(?:YOUR|INSERT|TODO|PLACEHOLDER|REPLACE)[^>]*>", re.I)
LOREM_RE = re.compile(r"\blorem ipsum\b", re.I)

# Fences that legitimately contain no code.
NON_EMPTY_EXEMPT_LANGS = {"text", "output", "console", "diff", "log"}


def slugify(heading: str) -> str:
    """GitHub's heading-to-anchor algorithm, near enough for link checking."""
    s = heading.strip().lower()
    s = re.sub(r"`([^`]*)`", r"\1", s)  # inline code
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)  # links -> text
    s = re.sub(r"[^\w\s-]", "", s)  # drop punctuation
    s = re.sub(r"\s+", "-", s.strip())
    return s


def collect_headings(text: str) -> list[tuple[int, str, int]]:
    """(level, title, lineno) for headings outside fenced blocks."""
    out: list[tuple[int, str, int]] = []
    in_fence = False
    fence_marker = ""
    for i, line in enumerate(text.splitlines(), 1):
        m = FENCE_RE.match(line)
        if m:
            if not in_fence:
                in_fence, fence_marker = True, m.group(2)[0]
            elif line.strip().startswith(fence_marker * 3):
                in_fence, fence_marker = False, ""
            continue
        if in_fence:
            continue
        h = HEADING_RE.match(line)
        if h:
            out.append((len(h.group(1)), h.group(2), i))
    return out


def collect_anchors(text: str) -> set[str]:
    anchors = {slugify(h[1]) for h in collect_headings(text)}
    anchors |= {a.lower() for a in HTML_ANCHOR_RE.findall(text)}
    return anchors


def resolve_link(source: str, target: str) -> tuple[bool, str]:
    """Resolve a link target relative to the doc. Returns (ok, detail)."""
    if target.startswith(("http://", "https://", "mailto:", "tel:")):
        return True, "external"
    if target.startswith("#"):
        return True, "same-file anchor"
    path_part, _, anchor = target.partition("#")
    if not path_part:
        return True, "anchor only"
    base = (REPO_ROOT / source).parent
    resolved = (base / path_part).resolve()
    try:
        rel = resolved.relative_to(REPO_ROOT.resolve())
    except ValueError:
        return False, f"escapes the repository ({path_part})"
    if not resolved.exists():
        return False, f"target does not exist ({rel})"
    if anchor and resolved.suffix == ".md":
        try:
            dest_text = resolved.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return False, f"cannot read target ({exc})"
        if anchor.lower() not in collect_anchors(dest_text):
            return False, f"target file exists but has no heading '{anchor}' in {rel}"
    return True, "ok"


def check_doc(doc: str, text: str, report: Report, *, manifest_docs: set[str]) -> None:
    lines = text.splitlines()

    # ── D1 headings ──────────────────────────────────────────────────────────
    headings = collect_headings(text)
    h1s = [h for h in headings if h[0] == 1]
    if not h1s:
        report.error("D1-no-h1", "document has no H1 heading", path=doc)
    elif len(h1s) > 1:
        report.error(
            "D1-multiple-h1",
            f"{len(h1s)} H1 headings (first at line {h1s[0][2]}, next at line {h1s[1][2]})",
            path=doc,
            hint="One H1 per document; demote the rest.",
        )
    prev = 0
    for level, title, lineno in headings:
        if prev and level > prev + 1:
            report.error(
                "D1-skipped-level",
                f"heading level jumps H{prev} -> H{level} at {title!r}",
                path=doc,
                line=lineno,
            )
        prev = level

    # ── D2 fences ────────────────────────────────────────────────────────────
    in_fence = False
    fence_start = 0
    fence_lang = ""
    fence_body: list[str] = []
    for i, line in enumerate(lines, 1):
        m = FENCE_RE.match(line)
        if m:
            if not in_fence:
                in_fence, fence_start, fence_lang, fence_body = True, i, m.group(3), []
            else:
                in_fence = False
                if (
                    not any(b.strip() for b in fence_body)
                    and fence_lang not in NON_EMPTY_EXEMPT_LANGS
                ):
                    report.error(
                        "D2-empty-fence",
                        f"code block opened at line {fence_start} is empty",
                        path=doc,
                    )
            continue
        if in_fence:
            fence_body.append(line)
    if in_fence:
        report.error(
            "D2-unclosed-fence",
            f"code block opened at line {fence_start} is never closed",
            path=doc,
        )

    # ── D3 links ─────────────────────────────────────────────────────────────
    for i, line in enumerate(lines, 1):
        for text_, target in LINK_RE.findall(line):
            ok, detail = resolve_link(doc, target)
            if not ok:
                report.error(
                    "D3-broken-link",
                    f"[{text_[:40]}]({target}) — {detail}",
                    path=doc,
                    line=i,
                )

    # ── D4 backticked paths ──────────────────────────────────────────────────
    for i, line in enumerate(lines, 1):
        for candidate in BACKTICK_PATH_RE.findall(line):
            if candidate.startswith(("http", "/", "~")):
                continue
            # A path mentioned relative to a subdir is common; try repo root and doc dir.
            if (REPO_ROOT / candidate).exists():
                continue
            if ((REPO_ROOT / doc).parent / candidate).exists():
                continue
            report.warn(
                "D4-stale-path",
                f"`{candidate}` does not exist from the repo root or the doc's directory",
                path=doc,
                line=i,
                hint="Update the reference or remove it.",
            )

    # ── D5 freshness header ──────────────────────────────────────────────────
    if doc in manifest_docs:
        header = "\n".join(lines[:20])
        has_updated = re.search(r"\*\*Last Updated\*\*|\*\*Updated\*\*|Last updated:", header, re.I)
        has_status = re.search(r"\*\*Status\*\*|^status:", header, re.I | re.M)
        if not has_updated:
            report.warn(
                "D5-no-freshness",
                "no '**Last Updated**' declaration in the first 20 lines",
                path=doc,
                hint="Staleness must be visible to a reader, not only to a tool.",
            )
        if not has_status:
            report.warn(
                "D5-no-status", "no '**Status**' declaration in the first 20 lines", path=doc
            )

    # ── D6 drift markers ─────────────────────────────────────────────────────
    markers = len(re.findall(r"\b(TODO|FIXME|XXX|HACK)\b", text))
    if markers:
        report.warn("D6-drift-markers", f"{markers} TODO/FIXME/XXX marker(s)", path=doc)

    # ── D7 placeholders ──────────────────────────────────────────────────────
    for i, line in enumerate(lines, 1):
        for ph in PLACEHOLDER_RE.findall(line):
            report.warn("D7-placeholder", f"unreplaced placeholder {ph}", path=doc, line=i)
        if LOREM_RE.search(line):
            report.warn("D7-lorem", "lorem ipsum text", path=doc, line=i)

    # ── D8 whitespace ────────────────────────────────────────────────────────
    trailing = [i for i, line in enumerate(lines, 1) if line != line.rstrip() and line.strip()]
    if trailing:
        report.warn(
            "D8-trailing-whitespace",
            f"{len(trailing)} line(s) with trailing whitespace (first at {trailing[0]})",
            path=doc,
        )


def read_doc(doc: str, *, source: str) -> str:
    """Read a doc from the index (default) or the worktree.

    The index is the default on purpose: during a `git stash`-using pre-commit hook the worktree
    can briefly hold a state that is neither the index nor HEAD, and a check that reads it can
    pass on a tree that does not exist. The worktree mode exists for the *gate*, which runs on
    committed-or-staged content where the worktree IS the intended state, and for iterating on a
    fix before staging it.
    """
    if source == "index":
        try:
            return read_from_index(doc)
        except RuntimeError:
            pass  # not in the index yet (new file) — fall through to the worktree
    p = REPO_ROOT / doc
    if not p.exists():
        raise FileNotFoundError(doc)
    return p.read_text(encoding="utf-8", errors="replace")


def main(argv: list[str]) -> int:
    quiet = "--quiet" in argv
    source = "worktree" if "--worktree" in argv else "index"
    paths = [a for a in argv if not a.startswith("-")]

    sections, _ = load_manifest()
    manifest_docs = {s.doc for s in sections}
    docs = paths or tracked_markdown()

    report = Report()
    report.checked = len(docs)
    for doc in docs:
        try:
            text = read_doc(doc, source=source)
        except FileNotFoundError:
            report.error("read", "file not found in index or worktree", path=doc)
            continue
        check_doc(doc, text, report, manifest_docs=manifest_docs)
        # A doc claiming standalone must carry a real, dated reason.
        if doc not in manifest_docs and not standalone_reason(doc, text):
            report.error(
                "D9-standalone-undated",
                "not in the manifest and no dated 'standalone, reviewed YYYY-MM-DD: reason'",
                path=doc,
            )

    if quiet:
        for f in report.errors + report.warnings:
            print(f.render())
    else:
        print(report.render("docs structure"))
        if report.warnings:
            print(f"   ({len(report.warnings)} warning(s) — warnings do not fail the gate)")
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
