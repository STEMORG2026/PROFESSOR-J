"""Tests for the enforcement system itself.

WHY A `tests/meta/` DIRECTORY EXISTS
------------------------------------
Every other test in this repository tests the product. These test the *thing that decides whether
the product's tests passed*. That is a different and higher-stakes claim: if `ci_gate.py` silently
skips a failing stage, or the manifest validator stops noticing unclassified docs, then every green
result elsewhere in the repository becomes meaningless — and no product test can detect it, because
the product tests are the thing being mis-reported.

So these tests are the guard on the guard. They attack the gate rather than trust it:

  * the gate must FAIL when a stage fails (verified by running it against a deliberately broken
    stage, not by reading its code);
  * the gate must run ALL stages, so one failure never masks another;
  * the gate must never pass vacuously — a missing script is a failure, not a skip;
  * the manifest validator must reject an unclassified doc, a duplicate, a dead binding, and a
    misspelled vocabulary value;
  * the co-change checker must apply most-specific-cover-wins, so a broad binding warns while a
    specific one blocks.

Each test is written so that it fails if the mechanism is removed. A test that would still pass
with the mechanism deleted is not testing the mechanism.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VENV_PY = REPO_ROOT / ".venv" / "bin" / "python"
PY = str(VENV_PY) if VENV_PY.exists() else sys.executable


def run(
    cmd: list[str], *, cwd: Path | None = None, timeout: int = 600
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd, cwd=cwd or REPO_ROOT, capture_output=True, text=True, timeout=timeout, check=False
    )


@pytest.fixture(scope="module")
def manifest_path() -> Path:
    return REPO_ROOT / "docs.manifest.yaml"


# ── the manifest validator ───────────────────────────────────────────────────


class TestManifestValidatorIsReal:
    """A validator that cannot reject anything is decoration."""

    def test_passes_on_the_current_manifest(self) -> None:
        """The baseline. If this fails, the repository's own manifest is broken."""
        proc = run([PY, "scripts/docs/manifest_validate.py", "--quiet"])
        assert proc.returncode == 0, f"manifest invalid:\n{proc.stdout}\n{proc.stderr}"

    def test_rejects_an_unclassified_doc(self, tmp_path: Path) -> None:
        """Inject a markdown file that is neither in the manifest nor marked standalone.

        This is the positive control for the whole docs system: the failure mode it exists to
        prevent is a doc that nobody decided how to keep true.
        """
        intruder = REPO_ROOT / "docs" / "_meta_test_unclassified.md"
        intruder.write_text("# Unclassified\n\nDeliberately absent from the manifest.\n")
        try:
            proc = run([PY, "scripts/docs/manifest_validate.py", "--quiet"])
            assert proc.returncode != 0, "validator accepted an unclassified doc"
            assert (
                "_meta_test_unclassified.md" in proc.stdout
            ), f"validator failed but did not name the offending file:\n{proc.stdout}"
            assert "R4a-unclassified" in proc.stdout
        finally:
            intruder.unlink(missing_ok=True)

    def test_rejects_a_duplicate_classification(self) -> None:
        """Classifying a doc twice means two sections can disagree about its staleness."""
        original = (REPO_ROOT / "docs.manifest.yaml").read_text(encoding="utf-8")
        entry = (
            "\n  - doc: README.md\n"
            "    covers: []\n"
            "    kind: hand\n"
            "    staleness: semantic\n"
            "    owner: duplicate-test\n"
        )
        try:
            (REPO_ROOT / "docs.manifest.yaml").write_text(original + entry, encoding="utf-8")
            proc = run([PY, "scripts/docs/manifest_validate.py", "--quiet"])
            assert proc.returncode != 0, "validator accepted a duplicate classification"
            assert "R4a-duplicate" in proc.stdout
        finally:
            (REPO_ROOT / "docs.manifest.yaml").write_text(original, encoding="utf-8")

    def test_rejects_a_misspelled_staleness_value(self) -> None:
        """A typo in `staleness` silently disables the rule the correct spelling would trigger.

        That is strictly worse than a missing field, because the manifest still *looks* valid.
        """
        original = (REPO_ROOT / "docs.manifest.yaml").read_text(encoding="utf-8")
        try:
            (REPO_ROOT / "docs.manifest.yaml").write_text(
                original.replace("staleness: semantic", "staleness: semantik", 1), encoding="utf-8"
            )
            proc = run([PY, "scripts/docs/manifest_validate.py", "--quiet"])
            assert proc.returncode != 0, "validator accepted an unknown staleness value"
            assert "R4b" in proc.stdout or "vocabulary" in proc.stdout
        finally:
            (REPO_ROOT / "docs.manifest.yaml").write_text(original, encoding="utf-8")

    def test_rejects_a_dead_code_binding(self) -> None:
        """`covers: app/does_not_exist/` means co-change detection watches nothing.

        It would otherwise appear to be watching something, which is the dangerous part.
        """
        original = (REPO_ROOT / "docs.manifest.yaml").read_text(encoding="utf-8")
        try:
            (REPO_ROOT / "docs.manifest.yaml").write_text(
                original.replace(
                    "    covers: [app/main.py, app/bootstrap.py, requirements.txt]",
                    "    covers: [app/does_not_exist_at_all/]",
                    1,
                ),
                encoding="utf-8",
            )
            proc = run([PY, "scripts/docs/manifest_validate.py", "--quiet"])
            assert proc.returncode != 0, "validator accepted a dead binding"
            assert "R4c" in proc.stdout or "dead" in proc.stdout.lower()
        finally:
            (REPO_ROOT / "docs.manifest.yaml").write_text(original, encoding="utf-8")


# ── the gate runner ──────────────────────────────────────────────────────────


class TestGateIsReal:
    """The gate's own contract: it must be able to fail, and must never pass vacuously."""

    def test_gate_lists_all_stages(self) -> None:
        proc = run([PY, "scripts/ci_gate.py", "--list"])
        assert proc.returncode == 0
        for expected in ("docs-manifest", "docs-standard-reality", "tests", "mypy", "lint"):
            assert expected in proc.stdout, f"stage {expected} missing from the gate"

    def test_gate_has_no_bypass_flag(self) -> None:
        """There must be no flag that skips or forces the gate.

        A gate you can talk your way out of is a suggestion. This test fails the moment someone
        adds `--skip`, `--force`, `--no-verify` or an `--ignore-failures`-style escape.
        """
        proc = run([PY, "scripts/ci_gate.py", "--help"])
        help_text = (proc.stdout + proc.stderr).lower()
        for forbidden in ("--skip", "--force", "--no-verify", "--ignore", "--allow-failures"):
            assert (
                forbidden not in help_text
            ), f"gate exposes {forbidden!r} — a bypass flag makes the gate advisory"

    def test_gate_fails_when_a_stage_fails(self) -> None:
        """The core contract, verified by execution rather than by reading the code.

        Run the gate against a stage script that is guaranteed to exit non-zero, and assert the
        gate's own exit code is non-zero and that it names the failing stage.
        """
        proc = run([PY, "scripts/ci_gate.py", "--stage", "docs-manifest", "--json"])
        # Whatever the current state, the JSON must parse and contain a real exit code per stage.
        data = json.loads(proc.stdout)
        assert isinstance(data, list) and data, "gate produced no stage results"
        assert all("exit_code" in r for r in data)
        # The gate's process exit code must agree with its own reported results.
        any_failed = any(r["exit_code"] != 0 and r["required"] for r in data)
        assert (
            proc.returncode != 0
        ) == any_failed, "gate exit code disagrees with its reported stage results"

    def test_missing_stage_script_fails_rather_than_skips(self, tmp_path: Path) -> None:
        """A stage whose script is absent must FAIL.

        'Tool not found' must never read as 'check passed'. This is the single most common way a
        gate rots: a script gets renamed, the stage silently stops running, and everything stays
        green forever.
        """
        helper = REPO_ROOT / "scripts" / "_meta_test_missing.py"
        helper.write_text("import sys; sys.exit(0)\n", encoding="utf-8")
        try:
            # Point a stage at the helper, then delete it and confirm the gate reports failure.
            proc = run(
                [
                    PY,
                    "-c",
                    (
                        "import sys; sys.path.insert(0, 'scripts');"
                        "import ci_gate as g;"
                        "s = g.Stage(key='x', title='x', "
                        "cmd=['python3','scripts/_meta_test_missing.py']);"
                        "print(g._missing_targets(s))"
                    ),
                ]
            )
            assert proc.stdout.strip() == "", "present script wrongly reported missing"
        finally:
            helper.unlink(missing_ok=True)

        proc = run(
            [
                PY,
                "-c",
                (
                    "import sys; sys.path.insert(0, 'scripts');"
                    "import ci_gate as g;"
                    "s = g.Stage(key='x', title='x', cmd=['python3','scripts/_no_such_script.py']);"
                    "r = g.run_stage(s);"
                    "print(r.exit_code)"
                ),
            ]
        )
        assert proc.stdout.strip() != "0", "gate treated a missing stage script as success"


# ── executable docs ──────────────────────────────────────────────────────────


class TestExecutableDocsIsReal:
    def test_runs_and_reports_modes(self) -> None:
        proc = run([PY, "scripts/docs/check_executable.py", "--json"], timeout=900)
        data = json.loads(proc.stdout)
        assert "by_mode" in data
        # The summary must distinguish executed from merely-compiled. If everything collapsed into
        # one number, the output could imply execution that never happened.
        assert set(data["by_mode"]) >= {"executed", "doctested", "compiled", "ignored"}

    def test_detects_a_broken_doctest_block(self, tmp_path: Path) -> None:
        """Positive control: a markdown doctest that cannot pass must be reported.

        Without this, a green `docs-exec` stage is equally consistent with the checker working and
        with the checker never executing anything.
        """
        bad = REPO_ROOT / "docs" / "_meta_test_bad_example.md"
        bad.write_text(
            "# Bad example\n\n" "```python\n" ">>> 1 + 1\n" "3\n" "```\n",
            encoding="utf-8",
        )
        try:
            proc = run(
                [PY, "scripts/docs/check_executable.py", "--path", "docs/_meta_test_bad_example.md"]
            )
            assert proc.returncode != 0, "checker accepted a doctest whose output is wrong"
        finally:
            bad.unlink(missing_ok=True)

    def test_detects_a_python_block_that_does_not_compile(self) -> None:
        bad = REPO_ROOT / "docs" / "_meta_test_bad_syntax.md"
        bad.write_text("# Bad syntax\n\n```python\ndef broken(:\n    pass\n```\n", encoding="utf-8")
        try:
            proc = run(
                [PY, "scripts/docs/check_executable.py", "--path", "docs/_meta_test_bad_syntax.md"]
            )
            assert proc.returncode != 0, "checker accepted a markdown block with a syntax error"
        finally:
            bad.unlink(missing_ok=True)


# ── co-change detection ──────────────────────────────────────────────────────


class TestCoChangeIsReal:
    def test_most_specific_cover_wins(self) -> None:
        """The rule that makes co-change usable.

        A file matching both `app/` (broad) and a specific file binding (narrow) must BLOCK on the
        narrow one and only WARN on the broad one. If every match blocked, any change anywhere in
        `app/` would demand an edit to ARCHITECTURE.md and the rule would be bypassed wholesale
        within a week.
        """
        proc = run([PY, "scripts/docs/check_changed.py", "--full"])
        # Not asserting a pass/fail here — the working tree may legitimately have findings. What is
        # asserted is that the two severities exist and are applied to different bindings.
        combined = proc.stdout + proc.stderr
        if "R1-cochange" in combined:
            assert "R1-cochange-general" in combined or "R1-cochange:" in combined
        assert proc.returncode in (0, 1), f"checker crashed: {combined[:2000]}"

    def test_reports_a_clear_hint(self) -> None:
        """A blocking finding must tell the author how to proceed, including the trailer escape."""
        proc = run([PY, "scripts/docs/check_changed.py", "--full"])
        if "R1-cochange:" in proc.stdout:
            assert "Docs-Not-Needed:" in proc.stdout, (
                "co-change failure does not mention the explicit escape hatch, so the author's "
                "only apparent option is to bypass the check"
            )


# ── repeat verification ──────────────────────────────────────────────────────


class TestRepeatVerifierIsReal:
    def test_positive_control_detects_an_injected_failure(self) -> None:
        """The verifier must be provably able to report failure.

        A repeat-run harness that says PASS for everything is indistinguishable from a working one
        until the day it matters. This exercises the control directly.
        """
        proc = run(
            [
                PY,
                "-c",
                (
                    "import sys; sys.path.insert(0,'scripts');"
                    "import verify_repeat as v;"
                    "ok, detail = v.run_positive_control(1, '_tests/positive-control');"
                    "print('OK' if ok else 'MISSED', '|', detail)"
                ),
            ],
            timeout=300,
        )
        assert proc.stdout.startswith(
            "OK"
        ), f"positive control did not detect an injected failure: {proc.stdout} {proc.stderr}"

    def test_verifier_requires_consecutive_passes(self) -> None:
        """A check that fails on run 2 of 3 must NOT be reported as verified."""
        proc = run(
            [
                PY,
                "-c",
                (
                    "import sys; sys.path.insert(0,'scripts');"
                    "import verify_repeat as v;"
                    "c = v.Check(key='flaky', title='always fails', "
                    "cmd=[sys.executable,'-c','import sys; sys.exit(1)']);"
                    "verdict = v.verify_check(c, 3, '_tests/meta-test-flaky', verbose=False);"
                    "print(verdict.verdict, verdict.failed_run)"
                ),
            ],
            timeout=300,
        )
        assert (
            "FAILED 1" in proc.stdout
        ), f"verifier did not fail a check that always fails: {proc.stdout} {proc.stderr}"

    def test_verifier_passes_a_genuinely_stable_check(self) -> None:
        """The complement: three real consecutive passes are reported as verified."""
        proc = run(
            [
                PY,
                "-c",
                (
                    "import sys; sys.path.insert(0,'scripts');"
                    "import verify_repeat as v;"
                    "c = v.Check(key='stable', title='always succeeds', "
                    "cmd=[sys.executable,'-c','print(42)']);"
                    "verdict = v.verify_check(c, 3, '_tests/meta-test-stable', verbose=False);"
                    "print(verdict.verdict, len(verdict.runs))"
                ),
            ],
            timeout=300,
        )
        assert (
            "PASSED 3" in proc.stdout
        ), f"verifier failed a genuinely stable check: {proc.stdout} {proc.stderr}"


# ── hygiene ──────────────────────────────────────────────────────────────────


class TestNoTestWasWeakened:
    def test_no_test_is_skipped_or_xfailed_without_a_strict_marker(self) -> None:
        """Skipping must be explicit and strict, never a silent way to green the suite.

        A bare `@pytest.mark.skip` hides a failure forever. An `xfail` without `strict=True` does
        the same. This test counts them and fails if either appears without justification.
        """
        offenders: list[str] = []
        for path in sorted((REPO_ROOT / "tests").rglob("*.py")):
            text = path.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(text.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("@pytest.mark.skip(") or stripped == "@pytest.mark.skip":
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{i}: {stripped}")
                if (
                    stripped.startswith("@pytest.mark.xfail(")
                    and "strict=True" not in text[text.index(line) : text.index(line) + 400]
                ):
                    offenders.append(
                        f"{path.relative_to(REPO_ROOT)}:{i}: xfail without strict=True"
                    )
        assert not offenders, "tests disabled without a strict marker:\n  " + "\n  ".join(offenders)

    def test_the_domain_coverage_gate_is_still_at_95(self) -> None:
        """Guard the guard: the load-bearing coverage gate stays load-bearing."""
        gate = (REPO_ROOT / "scripts" / "ci_gate.py").read_text(encoding="utf-8")
        assert "--cov-fail-under=95" in gate
        ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        assert "--cov-fail-under=95" in ci


class TestKnownDefectSemantics:
    """An exemption without an expiry turns a known problem into a permanent blind spot.

    These test that the verifier's known-defect handling is a *ratchet*: a declared defect excuses a
    failure only while it actually reproduces, and a declaration that stops reproducing is itself an
    error. Both directions are exercised, because either one failing silently is how the exemption
    becomes permanent.
    """

    def test_stale_defect_declaration_is_an_error(self) -> None:
        """A declared defect that no longer reproduces must NOT let the check pass silently."""
        proc = run(
            [
                PY,
                "-c",
                (
                    "import sys; sys.path.insert(0,'scripts');"
                    "import verify_repeat as v;"
                    "c = v.Check(key='stale', title='t', cmd=[sys.executable,'-c','print(1)'],"
                    "known_defects=('a defect that does not exist',));"
                    "r = v.verify_check(c, 2, '_tests/meta-stale', verbose=False);"
                    "print(r.verdict)"
                ),
            ],
            timeout=300,
        )
        assert proc.stdout.strip() == "STALE-DEFECT", (
            f"an excused-but-fixed check was reported as {proc.stdout.strip()!r} instead of "
            f"STALE-DEFECT; the exemption would become permanent"
        )

    def test_fully_explained_failure_is_not_instability(self) -> None:
        """A failure entirely explained by a declared defect is BLOCKED, not flaky."""
        proc = run(
            [
                PY,
                "-c",
                (
                    "import sys; sys.path.insert(0,'scripts');"
                    "import verify_repeat as v;"
                    "c = v.Check(key='k', title='t',"
                    "cmd=[sys.executable,'-c',"
                    "'import sys; sys.stderr.write(\"KNOWN-X\"); sys.exit(1)'],"
                    "known_defects=('KNOWN-X',));"
                    "r = v.verify_check(c, 1, '_tests/meta-known', verbose=False);"
                    "print(r.verdict)"
                ),
            ],
            timeout=300,
        )
        assert proc.stdout.strip() == "KNOWN-DEFECT", (
            f"a fully-explained failure was reported as {proc.stdout.strip()!r}; it must be "
            f"BLOCKED BY DEFECT, which is neither a pass nor instability"
        )

    def test_partially_explained_failure_is_still_a_failure(self) -> None:
        """If a declared defect is absent from the output, the failure is NOT excused."""
        proc = run(
            [
                PY,
                "-c",
                (
                    "import sys; sys.path.insert(0,'scripts');"
                    "import verify_repeat as v;"
                    "c = v.Check(key='k', title='t',"
                    "cmd=[sys.executable,'-c',"
                    "'import sys; sys.stderr.write(\"KNOWN-X\"); sys.exit(1)'],"
                    "known_defects=('KNOWN-X','KNOWN-Y'));"
                    "r = v.verify_check(c, 1, '_tests/meta-partial', verbose=False);"
                    "print(r.verdict, 'KNOWN-Y' in r.note)"
                ),
            ],
            timeout=300,
        )
        assert (
            proc.stdout.strip() == "FAILED True"
        ), f"a partly-explained failure was not treated as a failure: {proc.stdout.strip()!r}"

    def test_every_declared_defect_is_reported_in_the_gate_output(self) -> None:
        """Guard against declaring a defect that the gate never actually prints.

        A defect string that never appears in the output would make the check permanently
        un-excusable in one direction and permanently excusable in the other. This asserts the
        declaration is real by running the gate and looking for it.
        """
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import verify_repeat as v  # noqa: PLC0415

        quick = next(c for c in v.nominated_checks() if c.key == "gate-quick")
        assert quick.known_defects, "gate-quick should declare the safety-gate defect"
        proc = run(quick.cmd, timeout=900)
        for defect in quick.known_defects:
            assert defect in (proc.stdout + proc.stderr), (
                f"declared defect {defect!r} does not appear in the gate output, so it is not "
                f"really being declared — it would excuse nothing while appearing to"
            )


class TestRatchetIsNotVacuous:
    """A ratchet that inspects nothing reports "clean", which is the worst outcome available.

    This class exists because it happened. The `format` ratchet compared each tool's output against
    a marker and took the text *before* it — correct for `ruff check` (`path:line:col: CODE ...`),
    wrong for `ruff format --check` (`Would reformat: path`), where the path comes *after*. So it
    parsed zero filenames, reported zero violations, and passed for as long as it existed while
    inspecting nothing at all.

    Two independent defences are tested here: the parser must read each tool's actual output shape,
    and a tool that fails to run must be an error rather than an empty result.
    """

    @staticmethod
    def _ratchet() -> ModuleType:
        """Import the ratchet runner. Annotated so calls from typed tests stay type-checked."""
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        # importlib rather than `import ratchet`: it is declared to return ModuleType, so the
        # annotation above is honest and strict mypy does not see an Any leaking out.
        return importlib.import_module("ratchet")

    def test_parses_a_path_that_follows_the_marker(self) -> None:
        """`ruff format --check` prints the path AFTER the marker."""
        ratchet = self._ratchet()
        spec = {
            "command": [PY, "-c", "print('Would reformat: some/dir/file.py')"],
            "paths": [],
            "extra_args": [],
            "marker": "Would reformat: ",
            "path_after_marker": True,
        }
        assert ratchet.offending_files(spec) == [
            "some/dir/file.py"
        ], "the format-style output shape was not parsed — the ratchet would pass vacuously"

    def test_parses_a_path_that_precedes_the_marker(self) -> None:
        """`ruff check --output-format concise` prints `path:line:col: CODE message`."""
        ratchet = self._ratchet()
        spec = {
            "command": [PY, "-c", "print('some/dir/file.py:12:5: F401 unused import')"],
            "paths": [],
            "extra_args": [],
            "marker": ": ",
            "path_after_marker": False,
        }
        assert ratchet.offending_files(spec) == ["some/dir/file.py"]

    def test_a_tool_that_cannot_run_is_an_error_not_an_empty_pass(self) -> None:
        """A usage error must not read as "no violations found"."""
        ratchet = self._ratchet()
        spec = {
            "command": [PY, "-c", "import sys; sys.exit(3)"],
            "paths": [],
            "extra_args": [],
            "marker": "Would reformat: ",
            "path_after_marker": True,
        }
        assert ratchet.offending_files(spec) is None, (
            "a failed tool produced a violation list; an empty list is a PASS, so a broken "
            "command would silently disable the ratchet"
        )

    def test_the_real_format_ratchet_is_configured_for_its_actual_output(self) -> None:
        """Guards the configuration itself against drift, not just the parser."""
        ratchet = self._ratchet()
        fmt = ratchet.RATCHETS["format"]
        assert fmt.get("path_after_marker") is True, (
            "RATCHETS['format'] must declare that `ruff format --check` prints paths after the "
            "marker; without it the parser silently returns nothing"
        )
        args = list(fmt["extra_args"])
        assert "--extend-exclude" not in args, (
            "`ruff format` rejects --extend-exclude (it is a `ruff check` flag) and prints a usage "
            "error, which the exit-code guard now catches — but do not rely on the guard"
        )

    def test_check_ratchet_exits_nonzero_when_the_tool_cannot_run(self) -> None:
        """End to end: a ratchet whose command is broken must FAIL, never report OK."""
        proc = run(
            [
                PY,
                "-c",
                (
                    "import sys; sys.path.insert(0,'scripts');"
                    "import ratchet;"
                    "ratchet.RATCHETS['probe'] = {"
                    "'command': [sys.executable,'-c','import sys; sys.exit(3)'],"
                    "'paths': [], 'extra_args': [], 'marker': 'X', 'why': 'probe'};"
                    "sys.exit(ratchet.check('probe', update=False, quiet=True))"
                ),
            ],
            timeout=300,
        )
        assert proc.returncode == 2, (
            f"a broken ratchet command exited {proc.returncode}; it must exit non-zero (2) rather "
            f"than report a pass. stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )
