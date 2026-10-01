# BLOCKERS — Active

> A blocker stops work. If unresolvable without human input, mark **[NEEDS HUMAN]** and halt that
> line of work — do not guess.

| ID | Blocker | Blocks | Owner | Status | Resolution path |
|---|---|---|---|---|---|
| B1 | **Ruleset `main` cannot be re-armed.** The required check `Local gate, replayed on a clean runner` fails on a clean runner, and `bypass_actors: []` means no escape. Re-arming now would deadlock every PR permanently. | Any enforcement via GitHub | A7F3 | OPEN | Green the mirror first (§Next), then set `enforcement: active` |
| B2 | **`types-PyYAML` is undeclared**, so CI's mypy cannot type-check `yaml` importers. 5 CI mypy errors. | Green mirror, green `Lint & Typecheck` | A7F3 | OPEN | Declare it in `requirements.txt` |
| B3 | **Two stale `# type: ignore` comments** in `app/knowledge/pdf.py:59` and `app/telemetry/exporter.py:97` error under CI's installed versions. Fixing them is an **`app/` change**. | Green mirror | **[NEEDS HUMAN]** | OPEN | Authorize the `app/` edit, or pin the offending deps so the ignores stay valid |
| B4 | **"3 declared failures no longer fail"** — `tests/unit/knowledge/test_lhs_adapter.py::TestLHSSchemaContract::{test_real_export_structure,test_real_export_ids_unique,test_real_export_prerequisites_resolve}` pass on CI but fail locally. The gate correctly refuses a stale baseline. | Green mirror | A7F3 | OPEN | Make local and CI agree (venv sync / hermetic fixture), then re-tighten `declared_defects.py` |
| B5 | **`state/` markdown is not classified** in `docs.manifest.yaml`, so the docs gate would fail on `state/**`. | Committing the bootstrap | A7F3 | IN-PROGRESS | ADR-001: reasoned subtree exemption in the manifest validator |
