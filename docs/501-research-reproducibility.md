# Reproducibility

> Companion: `research-reproducibility` v0.1.0 from ProjectTemplates 0.1.0
> Answers here are this project's source of truth.
> Re-generate or adopt a newer template only as a deliberate decision (`tpl update`).

---

**Reproducibility commitment level.**

Full for engineering artifacts (tests, builds, coverage) and for research evaluations
(trials, citation audits, fault injection). Environment and dependency pinning included.

**Where artifacts live and how they are versioned.**

- Code + tests in the repo (versioned by git).
- Coverage/telemetry outputs → `artifacts/` or CI artifacts (derived, regenerable).
- Evaluation corpora and scripts under `tests/` or `evals/`.

**Environment and dependency pinning.**

- `requirements.txt` with pinned versions; `pyproject.toml` for tooling config.
- Node via `pnpm` lockfile.
- Python 3.11+; mypy strict; pinned CI images.

**Record keeping.**

- Every evaluation run logs parameters, model pool state, seeds, and results to the
  telemetry bus and `docs/adr/` where relevant.
- Changelog records versioned changes (`docs/600-changelog.md`).

**Instructions that let a stranger rerun end-to-end.**

1. `git clone` PROFESSOR-J.
2. `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.
3. Run verification (`AGENTS.md` §5).
4. Run `scripts/eval` entrypoints (Phase 9) for evaluation reproducibility.