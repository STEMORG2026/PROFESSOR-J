# Changelog

> Companion: `changelog` v0.1.0 from ProjectTemplates 0.1.0
> Answers here are this project's source of truth.
> Re-generate or adopt a newer template only as a deliberate decision (`tpl update`).

---

## Unreleased

### Changed (2026-08)
- **Branch consolidation:** merged the phase 0.6 governance hardening and phase 1 LHS
  consumer work onto `main` in one controlled integration (resolved `exceptions.py`,
  `scripts/board/review.py`, ledger conflicts).
- **LHS adapter tests made CI-portable:** replaced brittle live-export assertions
  (75 entities, machine-specific path) with a checked-in fixture (`tests/fixtures/`)
  plus a structural contract test against the real export (unique IDs, resolvable
  prerequisites, count agreement).
- **Correctness/hygiene:**
  - Dropped dead, conflicting LHS version constants from settings; the adapter owns
    the authoritative `0.1` contract.
  - Replaced all deprecated `datetime.utcnow()` uses with a tz-aware `utc_now()`
    helper (adds `app/domain/time.py`).
  - Removed the `app.skills.*` mypy exemption; skills now pass `--strict`.
- **Skills:**
  - `LHSTEMSkill` now queries the real `LHSKnowledgeAdapter` (get_concept, search,
    prerequisites, has_concept).
  - `web_search`/`code_execution`/`memory` return an honest `failure` with
    `not_implemented` instead of fake success (code_execution is DESTRUCTIVE tier).
- **Safety & guardrails (new `app/guardrails/`):** `@safety_gate` (SAFE/SENSITIVE/
  DESTRUCTIVE→HITL), `PromptInjectionDetector`, `PIIRedactor`; hypothesis-pinned
  tier×approval matrix.
- **Model pool (new `app/models/` + `app/resources/`):** `LLMProvider` interface with
  `MockProvider` + `OpenAICompatProvider`, `ProviderCatalog`, `ModelRouter` failover,
  `CircuitBreaker` (3-state), `TokenBudget`, `bounded_retry` (jittered backoff honoring
  `retry_after`).
- **Cognitive brain (new `app/brain/`):** minimal LangGraph pipeline (rule-based intent
  classification → deterministic plan from domain `ExecutionPlan` → synthesis via the
  router). langgraph added to the venv (already in `requirements.txt`).
- **Tests + robustness:** exhaustive grounded-over-generative matrix (ReviewStatus ×
  human-reviewed); route/breaker/retry fault-injection tests. Test count on `main`: 203.
- Docs reconciled against implemented state (`docs/300-architecture.md`,
  `IMPLEMENTATION-PLAN.md`, `docs/601-agents.md`, this changelog).

(-- follow the **Release discipline** notes below for commit links; the above is a
deliberate consolidation of the reconciling changes landed this cycle.)

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

### Added (2026-08) — Phase 3 Cognitive Engine (tutoring brain)
- **ProfessorAgent (`app/brain/professor.py`):** tutoring-mode Socratic prompts
  (Socratic Mentor / Expository Lecture / Exam Drill / Research Advisor), rule-based
  misconception diagnosis from the `MisconceptionType` catalog, prerequisite readiness
  gating, and grounded-vs-ungrounded responses sourced from the `LHSKnowledgeAdapter`.
  The Socratic scaffold mandates never revealing the final answer.
- **EvaluatorAgent (`app/brain/evaluator.py`):** deterministic rubric evaluation
  (numeric tolerance + accepted-principle terms) producing the domain `Evaluation`,
  and folds results into `LearnerState` mastery + misconception records.
- **Checkpointed tutorial loop (`app/brain/tutorial.py`):** `TutorialSession` compiles a
  LangGraph loop over a `MemorySaver` keyed by `thread_id = learner id`, so learner state
  resumes across calls and sessions. Snapshot serialisation round-trips enums as strings.
- **Simulated-student acceptance test:** a scripted learner passes Newton's 2nd Law —
  the professor scaffolds, diagnoses `heavier_falls_faster`, and only advances mastery on
  correct attempts (`tests/unit/brain/test_tutorial_loop.py`, `test_professor.py`,
  `test_evaluator.py`).

### Added (2026-08) — Phase 4 Platform Foundation (session / workspace / memory / tools)
- **Session subsystem (`app/session/`):** `SessionManager` over the domain `Session`/`Conversation`
  models; durable, resumable per-learner sessions via a pluggable `SessionStore` (in-memory +
  JSON-file). A session id doubles as the LangGraph checkpoint `thread_id`.
- **Workspace subsystem (`app/workspace/`):** `WorkspaceManager` enforces path-scope (no escaping
  the root) and size bounds on reads/writes; dispatch is tiered through the tool executor.
- **Memory subsystem (`app/memory/`):** abstract `MemoryBackend` (in-memory + JSON-file) behind a
  learner-namespaced `MemoryService` for durable, searchable cross-session recall. Seam for
  ChromaDB/BM25 later.
- **Tool executor (`app/tools/`):** `ToolExecutor` is the single safety choke point — tools register
  with a `SafetyTier` and every call runs through the safety policy (injection + PII + HITL for
  DESTRUCTIVE), failing closed on denial. Sandbox (Phase 5) and MCP invocation are future work.

---

## Release discipline

- Keep the top entry as **Unreleased** until a version is cut.
- Format per change: date, kind (added / changed / fixed / deprecated / removed),
  summary, and a link (commit or ADR).
- Note dependencies that changed alongside (e.g. LearningHubSTEM export version, provider
  catalogs, Python/Node versions).
