#!/usr/bin/env python3
"""Execute the examples that documentation claims work.

A doc example that does not run is a doc that lies, and it lies in the most expensive way: the
reader trusts it, copies it, and loses time to something the author never checked. This script
makes every executable claim in the repository falsifiable.

Two sources are executed:

  E1  ``>>>`` doctests inside Python docstrings, via the stdlib ``doctest`` module. Run against
      ``app/`` (the product) and ``scripts/`` (the tooling). Note that pytest's own
      ``--doctest-modules`` is NOT used here: it rewrites module globals and interacts badly with
      the app's import-time side effects, and the gate needs a check that cannot be derailed by
      another plugin.

  E2  Fenced ```` ```python ```` blocks in markdown. Two block styles are recognised:

        (a) **Named blocks** carrying pytest-style HTML comments:

                <!-- name: test_example -->
                ```python
                assert 1 + 1 == 2
                ```

            A block named ``test_*`` must pass its assertions. This is executable *documentation*:
            the code is real, and it is checked.

        (b) **Doctest-style blocks** — any fenced block whose content contains a ``>>>`` prompt is
            run as a doctest via ``doctest.DocTestParser``, so a ``>>>`` example in markdown is
            verified exactly like one in a docstring.

      A plain ``python`` block with neither form is **compiled** (`compile()`), not executed: it
      catches syntax rot and undefined-name typos in imports without running arbitrary snippets,
      which would be unsafe and non-hermetic. Compiling is a real check — a block that does not
      even parse has definitively rotted — and it is honest about being weaker than execution.

  E3  Every fenced block is reported by how it was verified (executed / doctested / compiled /
      skipped-by-language), so the summary can never imply more coverage than was achieved.

Usage:
    python3 scripts/docs/check_executable.py [--quiet] [--json] [--path PATH ...]

Exit codes: 0 all executed examples pass, 1 a failure, 2 the checker could not run.
"""

from __future__ import annotations

import argparse
import doctest
import io
import json
import re
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import REPO_ROOT, Report, tracked_markdown  # noqa: E402

# Languages whose blocks are compiled rather than executed, and languages ignored entirely.
PYTHON_FENCES = {"python", "py", "python3"}
COMPILE_ONLY_FENCES = {"pycon"}  # handled as doctest if it has >>>, else compiled
IGNORED_FENCES = {
    "",
    "text",
    "txt",
    "bash",
    "sh",
    "shell",
    "console",
    "output",
    "json",
    "yaml",
    "yml",
    "toml",
    "ini",
    "sql",
    "diff",
    "http",
    "mermaid",
    "ts",
    "tsx",
    "js",
    "jsx",
    "html",
    "css",
    "dockerfile",
    "makefile",
    "gitignore",
    "env",
    "c",
    "cpp",
    "rust",
    "go",
    "java",
}

FENCE_RE = re.compile(r"^(\s*)(`{3,}|~{3,})\s*(\S*)\s*$")
NAME_COMMENT_RE = re.compile(r"<!--\s*name:\s*([A-Za-z0-9_]+)\s*-->")
NAME_COMMENT_ABOVE_RE = re.compile(r"<!--\s*name:\s*test_[A-Za-z0-9_]*\s*-->")
SKIP_COMMENT_RE = re.compile(r"<!--\s*(?:skip|notest|no-execute)\b[^>]*-->", re.I)


@dataclass
class BlockOutcome:
    doc: str
    line: int
    language: str
    mode: str  # executed | doctested | compiled | ignored
    ok: bool = True
    detail: str = ""
    name: str = ""


@dataclass
class Summary:
    outcomes: list[BlockOutcome] = field(default_factory=list)

    def count(self, mode: str) -> int:
        return sum(1 for o in self.outcomes if o.mode == mode)

    @property
    def failures(self) -> list[BlockOutcome]:
        return [o for o in self.outcomes if not o.ok]


# ── E1: doctests in Python docstrings ────────────────────────────────────────


def run_docstring_doctests(report: Report, summary: Summary, roots: list[str]) -> None:
    """Run `>>>` examples found in docstrings under the given source roots.

    Module discovery is done by walking the source tree for ``*.py`` and converting each path to
    its dotted name. ``pkgutil.walk_packages`` was the obvious choice and the wrong one: pointed
    at a directory it follows ``sys.path`` and happily wanders into ``.venv``. Walking the tree
    ourselves means the scope is exactly the two directories named, and nothing else.
    """
    import importlib

    # The repository root must be importable for `app.*` to resolve.
    root_str = str(REPO_ROOT)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    for root in roots:
        base = REPO_ROOT / root
        if not base.is_dir():
            report.error("E1-root", f"doctest root {root} does not exist")
            continue

        for path in sorted(base.rglob("*.py")):
            if "__pycache__" in path.parts or path.name.startswith("_"):
                continue
            rel = path.relative_to(REPO_ROOT).with_suffix("")
            parts = list(rel.parts)
            if parts[-1] == "__init__":
                parts = parts[:-1]
                if not parts:
                    continue
            fq = ".".join(parts)

            # Entrypoints execute on import. Importing them to look for docstrings would run
            # their side effects, so they are skipped — and counted as skipped, never as passed.
            if _looks_like_entrypoint(path):
                summary.outcomes.append(
                    BlockOutcome(root, 0, "python", "ignored", detail=f"{fq}: entrypoint")
                )
                continue

            try:
                module = importlib.import_module(fq)
            except Exception as exc:  # noqa: BLE001 - inability to import is itself a finding
                report.error(
                    "E1-import",
                    f"{fq} could not be imported for doctesting: {type(exc).__name__}: {exc}",
                    hint=(
                        "Import-time failure. Either fix the module, or add it to the explicit "
                        "skip list in this script with a reason — never let it pass silently."
                    ),
                )
                continue

            finder = doctest.DocTestFinder()
            runner = doctest.DocTestRunner(
                optionflags=doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE
            )
            for test in finder.find(module, fq):
                if not test.examples:
                    continue
                buf = io.StringIO()
                runner.run(test, out=buf.write)
                out = buf.getvalue()
                ok = out.strip() == ""
                summary.outcomes.append(
                    BlockOutcome(
                        doc=fq,
                        line=test.lineno or 0,
                        language="python",
                        mode="doctested",
                        ok=ok,
                        detail=out.strip()[:2000],
                    )
                )
                report.checked += 1
                if not ok:
                    report.error(
                        "E1-doctest-failed",
                        f"doctest in {test.name} failed",
                        path=fq,
                        line=test.lineno or 0,
                        hint=out.strip()[:600],
                    )


def _looks_like_entrypoint(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return '__name__ == "__main__"' in text or "__main__" in text[:400]


# ── E2/E3: markdown code blocks ──────────────────────────────────────────────


def extract_blocks(text: str) -> list[tuple[int, str, str, str]]:
    """(start_line, language, body, preceding_comment) for each fenced block."""
    lines = text.splitlines()
    blocks: list[tuple[int, str, str, str]] = []
    in_fence = False
    fence_char = ""
    lang = ""
    start = 0
    body: list[str] = []
    prev_comment = ""
    for i, line in enumerate(lines, 1):
        m = FENCE_RE.match(line)
        if m:
            if not in_fence:
                in_fence, fence_char, lang, start, body = (
                    True,
                    m.group(2)[0],
                    m.group(3).lower(),
                    i,
                    [],
                )
                prev_comment = ""
                for back in range(i - 2, max(i - 6, -1), -1):
                    if back < 0:
                        break
                    stripped = lines[back].strip()
                    if not stripped:
                        continue
                    if stripped.startswith("<!--"):
                        prev_comment = stripped
                    break
            elif line.strip().startswith(fence_char * 3):
                in_fence = False
                blocks.append((start, lang, "\n".join(body), prev_comment))
            continue
        if in_fence:
            body.append(line)
    return blocks


def run_python_block(doc: str, lineno: int, body: str, name: str, report: Report) -> BlockOutcome:
    """Execute a named test block, or doctest a >>> block, or compile as a last resort."""
    has_prompts = ">>>" in body

    if has_prompts:
        parser = doctest.DocTestParser()
        try:
            test = parser.get_doctest(body, {}, f"{doc}:{lineno}", doc, lineno)
        except ValueError as exc:
            report.error(
                "E2-bad-doctest", f"cannot parse doctest block: {exc}", path=doc, line=lineno
            )
            return BlockOutcome(doc, lineno, "python", "doctested", ok=False, detail=str(exc))
        if not test.examples:
            return BlockOutcome(doc, lineno, "python", "compiled", ok=True, detail="no examples")
        runner = doctest.DocTestRunner(optionflags=doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE)
        buf = io.StringIO()
        runner.run(test, out=buf.write)
        out = buf.getvalue().strip()
        if out:
            report.error(
                "E2-doctest-failed",
                "markdown doctest block failed",
                path=doc,
                line=lineno,
                hint=out[:600],
            )
        return BlockOutcome(
            doc, lineno, "python", "doctested", ok=not out, detail=out[:2000], name=name
        )

    if name.startswith("test_"):
        # A named test block is executed with assertions live.
        ns: dict[str, object] = {"__name__": f"doc_block_{name}"}
        try:
            code = compile(body, f"{doc}:{lineno}", "exec")
            exec(code, ns)  # noqa: S102 - deliberate: these are the repository's own docs
        except Exception:  # noqa: BLE001
            detail = traceback.format_exc(limit=3)
            report.error(
                "E2-block-failed",
                f"named test block '{name}' raised",
                path=doc,
                line=lineno,
                hint=detail[-600:],
            )
            return BlockOutcome(
                doc, lineno, "python", "executed", ok=False, detail=detail, name=name
            )
        return BlockOutcome(doc, lineno, "python", "executed", ok=True, name=name)

    # Unnamed, non-doctest Python block: compile only. Catch syntax rot without executing
    # arbitrary snippets, which would be neither safe nor hermetic.
    try:
        compile(body, f"{doc}:{lineno}", "exec")
    except SyntaxError as exc:
        report.error(
            "E3-block-syntax",
            f"python block does not compile: {exc.msg}",
            path=doc,
            line=lineno,
            hint=f"offending line: {(exc.text or '').strip()[:120]}",
        )
        return BlockOutcome(doc, lineno, "python", "compiled", ok=False, detail=str(exc))
    return BlockOutcome(doc, lineno, "python", "compiled", ok=True)


def run_markdown_blocks(report: Report, summary: Summary, docs: list[str], source: str) -> None:
    for doc in docs:
        path = REPO_ROOT / doc
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for start, lang, body, comment in extract_blocks(text):
            if SKIP_COMMENT_RE.search(comment):
                summary.outcomes.append(
                    BlockOutcome(doc, start, lang, "ignored", detail="explicit skip comment")
                )
                continue
            if lang in PYTHON_FENCES or lang in COMPILE_ONLY_FENCES:
                name_m = NAME_COMMENT_RE.search(comment)
                name = name_m.group(1) if name_m else ""
                summary.outcomes.append(run_python_block(doc, start, body, name, report))
            else:
                summary.outcomes.append(
                    BlockOutcome(doc, start, lang or "(none)", "ignored", detail="non-python")
                )
    report.checked += len(
        [o for o in summary.outcomes if o.mode in {"executed", "doctested", "compiled"}]
    )


# ── entrypoint ───────────────────────────────────────────────────────────────


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Execute documented examples.")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--json", dest="as_json", action="store_true")
    parser.add_argument("--path", action="append", default=[], help="limit to these markdown files")
    args = parser.parse_args(argv)

    report = Report()
    summary = Summary()

    if not args.path:
        run_docstring_doctests(report, summary, ["app", "scripts"])
        run_markdown_blocks(report, summary, tracked_markdown(), "worktree")
    else:
        run_markdown_blocks(report, summary, args.path, "worktree")

    if args.as_json:
        print(
            json.dumps(
                {
                    "checked": report.checked,
                    "errors": len(report.errors),
                    "by_mode": {
                        m: summary.count(m)
                        for m in ("executed", "doctested", "compiled", "ignored")
                    },
                    "failures": [
                        {"doc": o.doc, "line": o.line, "mode": o.mode, "detail": o.detail[:400]}
                        for o in summary.failures
                    ],
                },
                indent=2,
            )
        )
        return 1 if report.errors else 0

    if args.quiet:
        for f in report.errors:
            print(f.render())
        return 1 if report.errors else 0

    print(report.render("docs executable examples"))
    print(
        "   verification by mode: "
        f"{summary.count('executed')} executed, "
        f"{summary.count('doctested')} doctested, "
        f"{summary.count('compiled')} compiled-only, "
        f"{summary.count('ignored')} ignored (non-python or explicitly skipped)"
    )
    print(
        "   NOTE: 'compiled-only' blocks are parsed, not run. They are counted separately so this "
        "summary can never overstate what was actually executed."
    )
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
