#!/usr/bin/env python3
"""Validate docs.manifest.yaml — every doc classified exactly once, every binding real.

Runs in BOTH layers. Three things are enforced:

  R4a  Completeness. Every git-tracked ``*.md`` appears in exactly one manifest section, or
       declares an explicit ``standalone, reviewed YYYY-MM-DD: <reason>`` line in its header.
       A doc that is in neither place is an error, not a warning: an unclassified doc is one
       nobody has decided how to keep true. Subtrees listed in ``EXEMPT_SUBTREES`` are the
       single, reasoned exception, and the exemption is printed on every run.

  R4b  Vocabulary. ``kind`` and ``staleness`` must be from the closed sets. A typo here is worse
       than a missing field — ``staleness: contnet`` would silently disable the review rule that
       the correct spelling would have triggered.

  R4c  Binding reality. Every ``covers`` entry must resolve to something that exists, and a
       directory binding must actually contain code. This is what stops the manifest decaying
       into decoration: a doc can claim to cover ``app/telemetry/`` only while that directory
       exists and holds code. When a path is renamed, this check fails and the binding is fixed
       rather than quietly pointing at nothing.

Usage:
    python3 scripts/docs/manifest_validate.py [--quiet]

Exit codes:
    0  manifest is valid
    1  one or more errors
    2  the manifest itself could not be parsed
"""

from __future__ import annotations

import sys
from collections import Counter
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

# Subtrees exempt from per-file classification (R4a only).
#
# Each entry MUST carry a written reason, and the exemption is printed on EVERY run so it stays
# visible rather than becoming folklore. An exemption cannot weaken R4b or R4c, because an exempted
# doc is not in the manifest at all — the vocabulary and binding checks simply have nothing to say
# about a file nobody classified.
#
# This exists because MACP's `state/` coordination surface changes on every agent session. Without
# a subtree rule, each new session file would fail the gate, and a gate that fails for bookkeeping
# reasons on every session is one agents learn to bypass — the exact failure mode this system
# exists to prevent. Rationale and rejected alternatives: state/DECISIONS.md ADR-001.
EXEMPT_SUBTREES: dict[str, str] = {
    "state/": (
        "MACP coordination surface: sessions/, plans/ and INDEX.md change on every agent session"
    ),
}


def _exempt_reason(doc: str) -> str | None:
    """Return the declared reason this doc's subtree is exempt from classification, or None."""
    for prefix, reason in EXEMPT_SUBTREES.items():
        if doc == prefix.rstrip("/") or doc.startswith(prefix):
            return reason
    return None


def _covers_target_exists(entry: str) -> tuple[bool, str]:
    """Resolve a `covers` entry. Returns (ok, detail).

    A binding is real if the path exists AND holds something a change could invalidate the doc
    over. "Holds Python" would be too narrow: `.github/` holds workflow YAML and `docs/adr/`
    holds decision records, and both are code-like artifacts a doc must move with. What is
    rejected is an existing-but-empty directory, because binding to one means co-change detection
    is watching nothing while appearing to watch something.
    """
    target = REPO_ROOT / entry.rstrip("/")
    if target.is_file():
        return True, "file"
    if target.is_dir():
        contents = [p for p in target.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
        if contents:
            return True, f"dir ({len(contents)} file(s))"
        return False, "directory exists but is empty"
    return False, "path does not exist"


def main(argv: list[str]) -> int:
    quiet = "--quiet" in argv

    sections, findings = load_manifest()
    report = Report(findings=list(findings))
    if not sections and report.errors:
        print(report.render("manifest-validate"))
        return 2

    # ── R4b is already applied by load_manifest; R4a and R4c here ─────────────

    seen = Counter(s.doc for s in sections)
    for doc, count in sorted(seen.items()):
        if count > 1:
            report.error(
                "R4a-duplicate",
                f"{doc} is classified {count} times",
                path="docs.manifest.yaml",
                hint="Each doc must have exactly one section; merge them.",
            )

    tracked = tracked_markdown()
    # Exempt subtrees leave the classification universe before counting, so `checked` reports the
    # docs that were genuinely expected to be classified rather than a number inflated by files
    # nobody is asked to classify.
    exempted = [doc for doc in tracked if _exempt_reason(doc)]
    classifiable = [doc for doc in tracked if not _exempt_reason(doc)]
    report.checked = len(classifiable)
    for doc in classifiable:
        if doc in seen:
            continue
        # Not in the manifest — it must declare itself standalone, read from the index so this
        # is consistent whether the file is committed or newly staged.
        try:
            source = read_from_index(doc)
        except RuntimeError:
            source = (REPO_ROOT / doc).read_text(encoding="utf-8", errors="replace")
        reason = standalone_reason(doc, source)
        if reason:
            continue
        report.error(
            "R4a-unclassified",
            "tracked doc is neither in the manifest nor marked standalone",
            path=doc,
            hint=(
                "Add a section to docs.manifest.yaml (doc + covers + kind + staleness + owner), "
                "or add to the file's header: 'standalone, reviewed YYYY-MM-DD: <reason>'."
            ),
        )

    for doc in sorted(seen):
        if doc not in tracked:
            report.error(
                "R4a-orphan",
                "manifest classifies a doc that is not tracked by git",
                path=doc,
                hint="Remove the section, or `git add` the file if it should be tracked.",
            )

    # ── R4c: every binding must resolve to real code ──────────────────────────
    bound = 0
    for section in sections:
        if section.doc not in tracked:
            continue
        for entry in section.covers:
            bound += 1
            ok, detail = _covers_target_exists(entry)
            if not ok:
                report.error(
                    "R4c-dead-binding",
                    f"`covers: {entry}` in the section for {section.doc}: {detail}",
                    path="docs.manifest.yaml",
                    hint=(
                        "Fix the path, or drop the binding if the doc no longer covers that code. "
                        "A binding that points at nothing means co-change detection is not "
                        "watching what you think it is watching."
                    ),
                )
        if section.kind == "generated":
            gen = section.generator
            if ":" not in gen:
                report.error(
                    "R4c-generator-form",
                    f"{section.doc}: generator must be '<script>:<function>'",
                    path="docs.manifest.yaml",
                )
            else:
                script = REPO_ROOT / gen.split(":", 1)[0]
                if not script.is_file():
                    report.error(
                        "R4c-generator-missing",
                        f"{section.doc}: generator script {gen.split(':', 1)[0]} does not exist",
                        path="docs.manifest.yaml",
                    )

    exemption_lines = [
        f"   exempt subtree {prefix} ({sum(1 for d in exempted if _exempt_reason(d) == reason)} "
        f"doc(s)): {reason}"
        for prefix, reason in EXEMPT_SUBTREES.items()
        if any(_exempt_reason(d) == reason for d in exempted)
    ]
    if not quiet:
        print(report.render("docs manifest"))
        print(
            f"   {len(sections)} section(s), {len(classifiable)} classifiable doc(s), "
            f"{bound} code binding(s)"
        )
        for line in exemption_lines:
            print(line)
    else:
        for line in exemption_lines:
            print(line)
        for f in report.errors:
            print(f.render())

    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
