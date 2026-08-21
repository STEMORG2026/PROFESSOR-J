# Changelog

> Companion: `changelog` v0.1.0 from ProjectTemplates 0.1.0
> Answers here are this project's source of truth.
> Re-generate or adopt a newer template only as a deliberate decision (`tpl update`).

---

## Unreleased

### Added (2026-08)
- Repository initialized as an independent peer repo (Phase 0).
- Governance suite: `docs/GOVERNANCE.md`, `docs/CONSTITUTION.md`, `docs/RULES.md`,
  `docs/STANDARDS.md`, `docs/PRINCIPLES.md`, `docs/WORKING-PROCEDURE.md`.
- Core documents: `AGENTS.md`, `PRD.md`, `ARCHITECTURE.md`, `ARCHITECTURE-ESSENTIALS.md`,
  `IMPLEMENTATION-PLAN.md`, `README.md`.
- Project Operating System foundation modules `docs/` answered for the general-purpose
  AI OS positioning.
- Product positioning: successor to JARVIS — renamed, upgraded, generalized.
- Backend scaffolding: `.venv/`, pinned `requirements.txt`, strict mypy config,
  pre-commit hooks, pytest smoke test (`1 passed`).

---

## Release discipline

- Keep the top entry as **Unreleased** until a version is cut.
- Format per change: date, kind (added / changed / fixed / deprecated / removed),
  summary, and a link (commit or ADR).
- Note dependencies that changed alongside (e.g. LearningHubSTEM export version, provider
  catalogs, Python/Node versions).
