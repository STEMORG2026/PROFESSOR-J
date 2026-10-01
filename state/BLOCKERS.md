# BLOCKERS — Active

> A blocker stops work. If unresolvable without human input, mark **[NEEDS HUMAN]** and halt that
> line of work — do not guess.

| ID | Blocker | Blocks | Owner | Status | Resolution path |
|---|---|---|---|---|---|
| B1 | **Ruleset `main` cannot be re-armed.** The required check `Local gate, replayed on a clean runner` fails on a clean runner, and `bypass_actors: []` means no escape. Re-arming now would deadlock every PR permanently. | Any enforcement via GitHub | A7F3 | OPEN | Green the mirror first (§Next), then set `enforcement: active` |
| B2 | ~~`types-PyYAML` undeclared~~ | — | A7F3 | **RESOLVED** | Declared `types-PyYAML` + `PyYAML` (`fb971ba`). `PyYAML` was also undeclared despite a direct runtime import in `app/authority/gateway.py`. |
| B3 | **Two stale `# type: ignore` comments** in `app/knowledge/pdf.py:59` and `app/telemetry/exporter.py:97` error under CI's installed versions. Fixing them is an **`app/` change**. | Green mirror | **[NEEDS HUMAN]** | OPEN | Authorize the `app/` edit, or pin the offending deps so the ignores stay valid |
| B4 | ~~3 declared failures no longer reproduce~~ | — | A7F3 | **RESOLVED** | Root cause: the tests assert a *sibling* repo's export and skip when absent, so they failed only where a stale export existed. They now skip with the reason; baseline 12 → 9. See DEBT D12. |
| B5 | ~~`state/` markdown unclassified~~ | — | A7F3 | **RESOLVED** | ADR-001 implemented in `scripts/docs/manifest_validate.py`: reasoned subtree exemption, printed on every run including `--quiet`, with 4 tests pinning its boundaries. |
