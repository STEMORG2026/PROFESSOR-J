# DASHBOARD — PROFESSOR-J

> **Executive summary. Read this first.**
> **Last Reconciled:** 2026-10-01T22:15Z
> **Reconciled by:** A7F3 (bootstrap + CI-greening agent, shutdown)
> **Repo:** STEMORG2026/PROFESSOR-J (public, org-owned) · default branch `main`

---

## 1. What this project is

PROFESSOR-J is a general-purpose autonomous AI platform (AI OS) in the STEM ecosystem
workspace. FastAPI backend, layered architecture (`domain` → `brain` → `adapters`), Next.js 15
frontend (Phase 7+, present but not the current focus). It inherits JARVIS's proven patterns at
the **pattern level only** — no package coupling.

## 2. Current state at a glance

| Area | State |
|---|---|
| Working tree | clean, on `fix/containment-48h` @ `164d631` |
| Local gate | **14/14 PASS** locally (no bypass flag) |
| CI mirror (clean runner) | **13/14** — `Tests` now green; `mypy` still red on 2 stale `type: ignore` in `app/` |
| Repeat verifier | 5/5 checks green over 3 consecutive runs |
| Test suite | 882 passed · 12 declared failures · 4 xfailed · 1 deselected (rate-measured) |
| Docs governance | 67 docs classified exactly once · 0 errors · 346 warnings |
| `main` CI | 🔴 every `ci.yml` job fails — see §4 |
| Ruleset `main` | ⚠️ **`evaluate` mode** (deliberately non-blocking) |
| Open PR | **#129** (`fix/containment-48h` → `main`) — `MERGEABLE`, unmerged |
| MACP | v2 adopted; protocol persisted at `state/PROTOCOL.md` |

## 3. Critical alerts

| # | Alert | Severity |
|---|---|---|
| A1 | Rule `main` is in `evaluate`, not `active`. Do **not** re-arm until the required check `Local gate, replayed on a clean runner` is green, or all PRs deadlock with no bypass. | 🔴 HIGH |
| A2 | `types-PyYAML` is installed in dev venvs but **not declared** in `requirements.txt`; CI cannot type-check the 5 modules that import `yaml`. | 🟠 MED |
| A3 | 5 tools/skill-modules lack `@safety_gate`. Verified **latent** (unreferenced) but `computer_use.py` launches processes via `subprocess.Popen`. | 🟠 MED |
| A4 | Local venv is **Python 3.14.7**; CI runs **3.11**. Gate can pass locally where CI cannot, for interpreter reasons. | 🟠 MED |
| A5 | Local branch `main` is behind `origin/main`. | 🟡 LOW |

## 4. Why `main`'s CI is red (root cause, verified)

For a long time every CI job died in **"Set up env"** before running a single test:
`pip install -r requirements.txt` failed with `ResolutionImpossible` because
`opentelemetry-exporter-otlp-proto-http==1.44.0` requires `opentelemetry-sdk~=1.44.0` while the
file pinned `sdk==1.29.0`.

**Fixed this session** (commit `9f690a2`), and `main` independently landed the same upgrade at
1.45.0 (dependabot #124/#125/#128), reconciled in merge `164d631`.

Jobs now actually run, which exposed the next layer:

| Job | Result | Cause |
|---|---|---|
| `Lint & Typecheck` | fail | mypy: 5× `Library stubs not installed for "yaml"` + 2 stale `type: ignore` |
| `Tests` | fail | whole-suite coverage 76% vs `--cov-fail-under=80`; authority tests need a sibling `../authority/allocation.yaml` |
| `Security scan` | fail | not yet diagnosed |
| `Local gate` (required) | fail | same mypy cause + "3 declared failures no longer fail — baseline is stale" |
| `Documentation gate` (required) | **pass** | — |

## 5. Recently completed (this session, branch `fix/containment-48h`)

- Local enforcement system: `scripts/ci_gate.py` (14 stages), `githooks/pre-push`, `verify_repeat.py`,
  `ratchet.py`, `declared_defects.py`.
- Documentation governance: `docs.manifest.yaml` + 5 checkers under `scripts/docs/`.
- Fixed 3 "passes while inspecting nothing" defects (vacuous co-change, format ratchet, and the
  uninstallable `requirements.txt`).
- Made `requirements.txt` installable again, then declared two undeclared dependencies.
- Adopted MACP v2 and persisted the protocol in-repo.
- Re-tightened the declared-defect baseline 12 → 9 after finding the declarations were
  environment-dependent (sibling-repo export absent on CI, stale locally).
- Corrected 4 stale "branch protection is impossible" claims.
- CI mirror advanced 12/14 → 13/14 (the `Tests` stage is green on a clean runner).

## 6. Next actions (priority order)

1. **Do not re-arm the ruleset** until (a) `types-PyYAML` is declared, (b) the 2 stale `type: ignore`
   comments are removed, (c) the declared-defect baseline is re-tightened for CI's environment.
2. Merge PR #129 in `evaluate` mode to land `gate-mirror.yml` + `quality-ratchets.yml` on `main`
   (required checks currently cannot exist on `main` without them).
3. Declare `types-PyYAML`; re-audit `requirements.txt` for other undeclared imports.
4. Reconcile `state/` with `docs.manifest.yaml` (see DECISIONS.md ADR-001).
5. Decide the 5 `@safety_gate` findings.
