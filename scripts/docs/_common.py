"""Shared helpers for the PROFESSOR-J documentation gate.

Design notes that matter:

* **Index-first.** Layer 1 (`check_changed.py`) must never read the working tree. Tools in this
  ecosystem have historically used `git stash` windows that make the worktree a "Frankenstein tree"
  — neither the index nor the commit — so any check that reads it can report a pass on a state that
  does not exist. Everything here reads either the index (`git show :path`) or an explicit commit.
  Layer 2 reads the worktree deliberately, because by then the index is the thing being committed.

* **No network.** Every check is offline. External-link checking is a separate scheduled concern;
  making it a pre-push dependency would make the gate fail for reasons the author cannot fix.

* **Explicit, closed vocabularies.** `kind` and `staleness` are validated against fixed sets. A
  misspelled value silently disables the rule that should have applied, which is worse than an
  error — so it is an error.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MANIFEST_PATH = REPO_ROOT / "docs.manifest.yaml"

# Closed vocabularies. See docs.manifest.yaml header for the meaning of each value.
VALID_KINDS = frozenset({"hand", "generated"})
VALID_STALENESS = frozenset({"facts", "content", "semantic", "snapshot"})

# A doc can opt out of the manifest by declaring this in its header block, with a date and a
# reason. Deliberately requires BOTH — an undated "standalone" is how a doc escapes governance
# forever, and a dateless reason cannot be reviewed for staleness.
STANDALONE_RE = re.compile(r"standalone,\s*reviewed\s+(\d{4}-\d{2}-\d{2})\s*:\s*(\S.*)", re.I)
HEADER_SCAN_LINES = 20

# Kinds of code path a `covers` entry may name.
_CODE_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".json", ".toml", ".cfg", ".yaml", ".yml", ".txt")
_CODE_ROOT_PREFIXES = ("app/", "scripts/", "tests/", "frontend/", ".github/")


@dataclass
class Finding:
    """One problem, with enough context to fix it without re-deriving anything."""

    rule: str
    message: str
    path: str = ""
    line: int = 0
    severity: str = "error"  # error | warning
    hint: str = ""

    def render(self) -> str:
        loc = self.path or "-"
        if self.line:
            loc = f"{loc}:{self.line}"
        out = f"[{self.severity.upper()}] {self.rule}: {loc}: {self.message}"
        if self.hint:
            out += f"\n        → {self.hint}"
        return out


@dataclass
class Report:
    """Accumulated findings for one rule set."""

    findings: list[Finding] = field(default_factory=list)
    checked: int = 0

    def error(self, rule: str, msg: str, **kw: Any) -> None:
        self.findings.append(Finding(rule, msg, severity="error", **kw))

    def warn(self, rule: str, msg: str, **kw: Any) -> None:
        self.findings.append(Finding(rule, msg, severity="warning", **kw))

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warning"]

    def render(self, title: str) -> str:
        lines = [f"── {title} ──", f"   checked {self.checked} item(s)"]
        for f in self.errors:
            lines.append("  " + f.render())
        for f in self.warnings:
            lines.append("  " + f.render())
        if not self.findings:
            lines.append("   OK")
        return "\n".join(lines)


# ── git plumbing ─────────────────────────────────────────────────────────────


def git(*args: str, check: bool = True) -> str:
    """Run a git command in the repo root and return stdout."""
    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def tracked_markdown() -> list[str]:
    """Every markdown file under governance: tracked **plus newly added untracked** ones.

    Including untracked files matters more than it looks. `git ls-files` alone reports only what is
    already committed, so a brand-new doc that nobody has staged yet is invisible to the validator —
    it escapes classification at exactly the moment someone is writing it, and only gets caught
    later (if their commit happens to run the gate, and by then they have moved on).

    That is not hypothetical: the first version of this function used `git ls-files` alone, and the
    meta-test `test_rejects_an_unclassified_doc` failed against it, which is how the hole was found.
    The guard caught the guard.

    `--exclude-standard` keeps gitignored trees out, so `frontend/node_modules/` (457 markdown
    files) does not enter the universe.
    """
    out = git("ls-files", "--cached", "--others", "--exclude-standard", "*.md")
    return sorted(line for line in out.splitlines() if line)


def staged_files() -> list[str]:
    """Files staged for commit (added/copied/modified/renamed). Deleted files excluded."""
    out = git("diff", "--cached", "--name-only", "--diff-filter=ACMR")
    return sorted(p for p in out.splitlines() if p)


def files_in_range(rev_range: str) -> list[str]:
    """Files changed in a commit range, e.g. 'origin/main..HEAD'."""
    out = git("diff", "--name-only", "--diff-filter=ACMR", rev_range)
    return sorted(p for p in out.splitlines() if p)


def read_from_index(path: str) -> str:
    """Read a file's staged content (`:path`), NOT the worktree.

    Layer 1 must be index-based: during a `git stash`-using hook (such as the native
    ruff/format hook) the worktree can momentarily hold a state that is neither the index nor
    HEAD. Reading `:path` is immune to that.
    """
    return git("show", f":{path}")


# ── manifest ─────────────────────────────────────────────────────────────────


@dataclass
class Section:
    doc: str
    covers: list[str]
    kind: str
    staleness: str
    owner: str
    generator: str = ""
    notes: str = ""


def load_manifest() -> tuple[list[Section], list[Finding]]:
    """Parse docs.manifest.yaml, returning (sections, structural_findings).

    Structural findings are returned rather than raised so the caller can report all problems in
    one run instead of making the author fix them one at a time.
    """
    import yaml  # local import: keeps `--help` working without pyyaml

    findings: list[Finding] = []
    if not MANIFEST_PATH.exists():
        findings.append(
            Finding(
                "manifest-missing",
                f"{MANIFEST_PATH.name} does not exist",
                hint="The docs manifest is the source of truth for doc classification.",
            )
        )
        return [], findings

    try:
        raw = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        findings.append(Finding("manifest-invalid-yaml", str(exc), path="docs.manifest.yaml"))
        return [], findings

    if not isinstance(raw, dict) or "sections" not in raw:
        findings.append(
            Finding("manifest-schema", "top level must be a mapping with a `sections` key")
        )
        return [], findings

    sections: list[Section] = []
    for idx, item in enumerate(raw["sections"]):
        where = f"docs.manifest.yaml sections[{idx}]"
        if not isinstance(item, dict):
            findings.append(Finding("manifest-schema", "section must be a mapping", path=where))
            continue
        missing = [k for k in ("doc", "covers", "kind", "staleness", "owner") if k not in item]
        if missing:
            findings.append(
                Finding(
                    "manifest-schema",
                    f"section {item.get('doc', '<no doc>')!r}: missing {', '.join(missing)}",
                    path=where,
                )
            )
            continue
        kind = item["kind"]
        staleness = item["staleness"]
        if kind not in VALID_KINDS:
            findings.append(
                Finding(
                    "manifest-vocabulary",
                    f"{item['doc']}: unknown kind {kind!r}",
                    path=where,
                    hint=f"Legal values: {', '.join(sorted(VALID_KINDS))}",
                )
            )
        if staleness not in VALID_STALENESS:
            findings.append(
                Finding(
                    "manifest-vocabulary",
                    f"{item['doc']}: unknown staleness {staleness!r}",
                    path=where,
                    hint=f"Legal values: {', '.join(sorted(VALID_STALENESS))}",
                )
            )
        if kind == "generated" and not item.get("generator"):
            findings.append(
                Finding(
                    "manifest-schema",
                    f"{item['doc']}: kind=generated requires a `generator`",
                    path=where,
                )
            )
        covers = item["covers"] or []
        if not isinstance(covers, list):
            findings.append(
                Finding("manifest-schema", f"{item['doc']}: `covers` must be a list", path=where)
            )
            covers = []
        sections.append(
            Section(
                doc=item["doc"],
                covers=[str(c) for c in covers],
                kind=kind,
                staleness=staleness,
                owner=str(item["owner"]),
                generator=str(item.get("generator", "")),
                notes=str(item.get("notes", "")),
            )
        )
    return sections, findings


def standalone_reason(path: str, source: str) -> str | None:
    """Return the declared standalone reason if this doc opts out of the manifest."""
    for line in source.splitlines()[:HEADER_SCAN_LINES]:
        m = STANDALONE_RE.search(line)
        if m:
            return m.group(2).strip()
    return None


def is_code_path(entry: str) -> bool:
    """Does a `covers` entry name code (as opposed to a doc or a bare directory)?"""
    e = entry.rstrip("/")
    if e.endswith(_CODE_SUFFIXES):
        return True
    return e.startswith(_CODE_ROOT_PREFIXES)
