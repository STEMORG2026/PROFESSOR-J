# Plan (PARTIAL — see status note at the end) — agent A7F3: reconcile `state/` with governance, then green the CI mirror

## Objective
Make the required GitHub status check `Local gate, replayed on a clean runner` pass on a clean
runner, so the branch ruleset can be safely set to `active` without deadlocking the repository —
while keeping the MACP `state/` directory governed rather than exempted by accident.

## Scope

**In scope**
- `scripts/docs/manifest_validate.py` + `docs.manifest.yaml`: reasoned subtree exemption for `state/`.
- `requirements.txt`: declare `types-PyYAML` (and `PyYAML`) — undeclared direct dependency.
- `scripts/declared_defects.py`: re-tighten the baseline once local and CI agree.
- `state/**`: MACP bookkeeping.
- Resolve PR #129 and the ruleset state.

**Out of scope (requires explicit authorization)**
- Any `app/` change. Specifically `app/knowledge/pdf.py:59` and `app/telemetry/exporter.py:97`
  (stale `type: ignore`) and `app/bootstrap.py` (safety-gate wiring). Report; do not fix.

## Approach
1. Implement ADR-001: subtree exemption with a mandatory written reason, printed on every validation
   run so it stays visible. Verify `manifest_validate.py` still catches unclassified docs elsewhere.
2. Declare the missing dependency; re-audit `requirements.txt` for other undeclared direct imports.
3. Sync the local venv to `requirements.txt` so local ≈ CI, then re-read the declared-defect
   baseline against reality and shrink it. (The gate *requires* a stale baseline to be tightened —
   it is not optional.)
4. Investigate `Security scan` (undiagnosed).
5. Re-run the gate; push; observe PR #129's checks.
6. Only if `Local gate` is green: `enforcement: active`, and fix `allowed_merge_methods` to
   `["squash","rebase"]` (it currently lists `merge`, contradicting `required_linear_history`).

## Risks & mitigations
| Risk | Mitigation |
|---|---|
| Subtree exemption becomes a loophole | Require a written reason; print the exemption every run; keep it one subtree |
| Re-arming the ruleset deadlocks all PRs | Guard: only re-arm after observing a green required check on a real PR |
| Venv sync changes local test outcomes | Expected and desired — it exposes the true CI state; re-baseline deliberately |
| Scope creep into `app/` | Hard stop; log `[BLOCKER]` and request authorization |

## Rollback
- Ruleset: `gh api -X PUT .../rulesets/<id> -f enforcement=evaluate` (non-blocking, instant).
- Manifest/validator: revert the commit; `state/` exemption is additive.
- Dependency declarations: revert `requirements.txt`; no runtime code changes involved.

## Success criteria
1. `manifest_validate.py` passes with `state/` present, and still fails on a genuinely
   unclassified doc outside `state/`.
2. `python scripts/ci_gate.py` → 14/14 locally.
3. PR #129 shows `Local gate, replayed on a clean runner` **green**.
4. Ruleset `active` with no deadlock, and `allowed_merge_methods` consistent with linear history.
5. Working tree clean; all work committed and pushed; `state/` updated.


---

## Status at shutdown — PARTIAL

| # | Success criterion | Result |
|---|---|---|
| 1 | Manifest passes with `state/` present; still fails on a genuinely unclassified doc outside it | ✅ met, with 4 boundary tests + a two-checker agreement test |
| 2 | `python scripts/ci_gate.py` → 14/14 locally | ✅ met |
| 3 | PR #129 shows `Local gate` **green** | ❌ **not met** — 13/14; `mypy` red on 2 stale `# type: ignore` in `app/` |
| 4 | Ruleset `active`, `allowed_merge_methods` consistent | ❌ not attempted — criterion 3 is its precondition |
| 5 | Tree clean; work committed and pushed; `state/` updated | ✅ met |

**Why it stopped:** the remaining fix is an `app/` change, which this agent is not authorized to
make. Recorded as B3 `[NEEDS HUMAN]`. Plan file retained (not deleted) because it is incomplete.
