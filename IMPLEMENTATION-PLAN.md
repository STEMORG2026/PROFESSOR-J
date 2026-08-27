# PROFESSOR-J — Implementation Plan & Roadmap

> **Master Engineering Roadmap**
> **Status:** Active Execution Plan
> **Phases:** 0 through 9
> **Related:** `PRD.md` (what), `ARCHITECTURE.md` (how), `docs/GOVERNANCE.md` (rules)

---

## 1. Roadmap Overview

```
PHASE 0  ░░░░░░░░░░  Governance, Workspace Setup & Bootstrap Foundation
PHASE 0.5░░░░░░░░░░  Foundation Hardening (Config, Logging, CI, ADRs, Langfuse)
PHASE 1  ░░░░░░░░░░  Core Domain Models & LearningHubSTEM Consumer Seam
PHASE 2  ░░░░░░░░░░  Multi-Provider Model Pool & Circuit Breakers
PHASE 3  ░░░░░░░░░░  Cognitive Engine (LangGraph) + Socratic Agents
PHASE 4  ░░░░░░░░░░  Platform Parity: Session, Workspace, Memory, Tools
PHASE 5  ░░░░░░░░░░  Code & Math Sandbox Execution Engine
PHASE 6  ░░░░░░░░░░  Knowledge, Research & PDF Ingestion Pipeline
PHASE 7  ░░░░░░░░░░  Next.js 15 Interactive Canvas UI
PHASE 8  ░░░░░░░░░░  WebRTC Real-Time Voice Classroom
PHASE 9  ░░░░░░░░░░  Mastery Tracking, Production & CI/CD Pipeline
```

---

## 2. Phase-by-Phase Execution Plan

### Phase 0: Governance, Workspace Setup & Bootstrap Foundation
- [x] Repository initialized as an independent peer repo (workspace governance).
- [x] Governance suite: `docs/GOVERNANCE.md`, `docs/CONSTITUTION.md`, `docs/RULES.md`,
      `docs/STANDARDS.md`, `docs/PRINCIPLES.md`, `docs/WORKING-PROCEDURE.md`.
- [x] Core documents: `AGENTS.md`, `PRD.md`, `ARCHITECTURE.md`,
      `ARCHITECTURE-ESSENTIALS.md`, `IMPLEMENTATION-PLAN.md`.
- [x] Project Operating System foundation answers in `docs/` foundation modules.
- [x] Initialize Python 3.11+ virtual environment (`.venv/`) and `requirements.txt`.
- [x] Set up pre-commit hooks, strict mypy config, pytest scaffolding.
- **Acceptance Criteria:** `pytest` runs and passes; directory structure verified.

### Phase 0.5: Foundation Hardening (Config, Logging, CI, ADRs, Langfuse)
- [x] **Pydantic Settings** (`app/config/settings.py`): `BaseSettings` with validation, `.env.example`, secret detection at startup.
- [x] **Structured Logging** (`app/logging_config.py`): JSON output, correlation IDs, log levels, OTel-ready.
- [x] **Error Taxonomy** (`app/exceptions.py`): Typed exceptions, retry policies, circuit breaker hooks.
- [x] **GitHub Actions CI** (`.github/workflows/ci.yml`): pytest, mypy strict, pre-commit, coverage gates, artifact upload.
- [x] **ADR Infrastructure**: Create `docs/adr/`, MADR template, write ADR-001 (successor decision), ADR-002 (pattern inheritance), ADR-003 (layered architecture + LangGraph).
- [x] **Secrets Validation**: Pre-commit + startup check for required env vars; fail fast on missing secrets.
- [x] **Makefile**: Common targets (`make test`, `make typecheck`, `make lint`, `make run`, `make eval`).
- [x] **Langfuse Self-Host** (docker-compose): Postgres + ClickHouse + Langfuse; OTel exporter config in `app/telemetry/exporter.py`.
- [x] **OTel Instrumentation**: OpenTelemetry SDK + semantic conventions (agent, tool, retrieval, guardrail, evaluator spans).
- **Acceptance Criteria:** `make test` / `make typecheck` / `make lint` all pass; CI green on push; ADRs rendered; Langfuse UI accessible; OTel spans visible in Langfuse.

> Note (reconciled 2026-08): all Phase 0.5 code artifacts exist and are merged on `main`; CI + mypy-strict + pre-commit are green. The remaining acceptance check is *runtime* verification against a running Langfuse instance (spans exported), which is an ops step, not an implementation gap.

### Phase 1: Core Domain Models & LearningHubSTEM Consumer Seam
- [x] Author pure Python dataclasses in `app/domain/` (`LearnerState`,
      `PedagogicalTurn`, `MisconceptionState`, `ConceptEntity`, `ExecutionPlan`,
      `ToolCallRequest`, `Session`, `Conversation`, `MasteryScore`).
- [x] Implement `app/knowledge/lhs_adapter.py` reading
      `LearningHubSTEM/exports/knowledge.json`; validate `export_version`/`schema_version` (currently `0.1`);
      prerequisite mapping from `mathematically_requires`/`logically_requires` relationship types.
- [x] Implement `GeneralKnowledgeAdapter` fallback (labeled ungrounded with source provenance).
- [ ] **Memory Backend Abstraction**: `MemoryBackend` protocol + `ChromaMemoryBackend` impl (pluggable for Qdrant/PGVector).
- [ ] **MCP Client Design** (Phase 1 deliverable): `MCPServerManager` interface, stdio + Streamable HTTP transports,
      `MCPToolSearch` for on-demand loading, `MCPRegistry` for caching.
- [x] Write unit tests: domain models (100%), LHS adapter (100% + zero-drift), prerequisite traversal,
      memory backend contract tests.
- **Acceptance Criteria:** 100% coverage for domain + adapters; MCP interfaces defined; memory backend swappable.

> Note (reconciled 2026-08): domain dataclasses, the LHS consumer adapter, the GeneralKnowledgeAdapter and
> their tests are merged on `main`. The memory backend and MCP client remain not-implemented (their contract
> work is scheduled within this phase's remaining scope). The contract version is `0.1` (both export and
> schema), as validated by `app/knowledge/lhs_adapter.py` — earlier references to version `3` were stale.

### Phase 2: Multi-Provider Model Pool & Circuit Breakers
- [x] **Provider Interface** (`app/models/providers.py`): `LLMProvider` (abstract), `LLMResult` (standardized),
      `complete`/stream signatures. Includes `MockProvider` (deterministic, tests/dev) and
      `OpenAICompatProvider` (any OpenAI-compatible `/chat/completions` endpoint).
- [ ] **Provider Implementations**: Port JARVIS's 17+ providers (Ollama, llama.cpp, OpenAI,
      Anthropic, Google, Groq, Cerebras, OpenRouter, Mistral, Cohere, Together, NVIDIA NIM,
      GitHub Models, HF, Cloudflare, Zhipu, xAI, etc.).
- [x] **Live Provider Catalog** (`app/models/catalog.py`): Dynamic discovery of endpoints;
      curated defaults + runtime registration; no hardcoded fallbacks.
- [x] **Circuit Breakers** (`app/resources/circuit_breaker.py`): 3-state (`CLOSED`, `OPEN`,
      `HALF_OPEN`); `TokenBudget` TPM/RPM accounting; auto-failover on 429/503; configurable cooldown.
- [~] **ModelRouter** (`app/models/router.py`): provider selection → failover; integrates with
      `TokenBudget` + circuit breakers. **Task-type classification → provider selection is not yet
      wired** (the router prefers an explicit provider; intent-driven selection is future work).
- [ ] **Bounded retry**: `bounded_retry()` (honors `retry_after`, jittered backoff) exists in
      `app/models/retry.py`; wiring it into the router's per-call path is pending.
- [x] **Tests** (`tests/unit/models/`, `tests/unit/resources/`): fault injection (rate-limit,
      timeout, auth, circuit-open), failover, breaker state transitions, budget caps, retry backoff.
- **Acceptance Criteria:** Router switches to fallback provider on simulated rate limits;
      catalog refreshes without restart; all 17+ providers register and health-check.

> Note (reconciled 2026-08): the model-pool *foundation* (typed providers, catalog, circuit breakers,
> budgets, router failover, bounded retry) is implemented and unit-tested on `main`. The breadth of
> shipping all 17+ real provider integrations, per-provider health checks, and task-type→provider
> routing remains to be done to fully satisfy Phase 2 acceptance.

### Phase 3: Cognitive Engine (LangGraph) + Socratic Agents
- [~] **LangGraph Integration** (`app/brain/`): `StateGraph` (TypedDict `BrainState`) with nodes
      for intent classification → plan construction → synthesis, conditional flow.
      **Checkpointing (pause/resume) and streaming are not yet implemented.**
- [~] **CognitiveBrain**: LangGraph node composition — intent classification → plan generation
      → synthesis via the model router. Guarded execution (safety gate) and streaming are future work.
- [ ] **ProfessorAgent** (subgraph): Tutoring modes (Socratic Mentor, Expository Lecture,
      Exam Drill, Research Advisor); misconception diagnosis; adaptive difficulty from mastery.
- [ ] **EvaluatorAgent**: SymPy step verification; diagnostic assessment; mastery tracking
      via `DatabaseEngine`.
- [ ] **ResearchAgent**: PDF ingestion → chunking → embedding → retrieval → cited synthesis;
      integrates with MCP for external search.
- [ ] **ToolExecutorAgent**: Sandbox dispatch; `@safety_gate` enforcement; MCP tool invocation
      via `MCPServerManager`; result synthesis.
- [ ] **Simulated Student Test**: Newton's 2nd Law pass — agent guides without revealing answer.
- **Acceptance Criteria:** LangGraph checkpointing works (pause/resume); simulated student
      passes Newton's 2nd Law; OTel spans emitted for each node.

> Note (reconciled 2026-08): a foundational `app/brain/` pipeline (rule-based intent classification →
> deterministic plan from the domain ExecutionPlan models → synthesis through the ModelRouter) is
> implemented and end-to-end tested against the deterministic MockProvider. The Professor/Evaluator/
> Research/ToolExecutor agents, checkpointing, streaming, and the simulated-student acceptance test
> are not yet done.

### Phase 4: Platform Parity — Session, Workspace, Memory, Tools
- [ ] Port `SessionManager` and `WorkspaceManager` from JARVIS patterns; integrate with
      LangGraph checkpointing (thread_id = session_id).
- [ ] Port hybrid memory (`MemoryService`: ChromaDB dense + BM25 sparse) behind abstract
      `MemoryBackend`; `ReflexionEngine` + `SkillSynthesizer` for self-improvement.
- [ ] Port `ToolExecutor` and tool registry behind `@safety_gate`; add `MCPToolExecutor`
      for MCP tool invocation.
- [ ] Enable general-purpose chat/file/workspace assistance (non-education paths).
- [ ] **MCP Integration Complete**: `MCPServerManager` fully implemented with stdio +
      Streamable HTTP; `MCPToolSearch` on-demand loading; `CodeExecutionTools` pattern.
- **Acceptance Criteria:** ≥ 90% of JARVIS capabilities operational; MCP tools invokable
      from agents; checkpointing + Langfuse traces visible for all operations.

### Phase 5: Code & Math Sandbox Execution Engine
- [ ] Implement `app/tools/sandbox.py` (Docker + gVisor isolation, CPU/memory limits,
      timeout watchdog, no network, PII redaction).
- [ ] **Local Inference**: Bundle `llama.cpp` (desktop); external Ollama server (server
      deployment); model quantization (Q4_K_M) for CPU-first UX.
- [ ] Implement SymPy solver tool (algebra, calculus, unit conversions).
- [ ] Implement Plotly/Matplotlib chart generator tool.
- [ ] Enforce `@safety_gate` tiers with HITL; audit logging for all DESTRUCTIVE calls.
- **Acceptance Criteria:** Sandbox prevents harmful filesystem calls and terminates
      infinite loops cleanly; bundled llama.cpp runs on CPU; OTel spans for sandbox events.

### Phase 6: Knowledge, Research & PDF Ingestion Pipeline
- [ ] Implement `ResearchAgent` for academic paper processing.
- [ ] Implement PDF text/table/formula extraction (`PyMuPDF` + `PaddleOCR`).
- [ ] Set up `ChromaVectorStore` wrapper and BM25 retriever in `app/memory/`.
- [ ] Implement citation provenance mapper (page number, bounding box, snippet).
- **Acceptance Criteria:** Ingested paper is queryable with exact page-level citations.

### Phase 7: Next.js 15 Interactive Canvas UI
- [ ] Scaffold `frontend/` with Next.js 15 App Router, React 19, Tailwind.
- [ ] Integrate `@lobehub/ui` dark holographic theme.
- [ ] Implement KaTeX equation renderer and Plotly chart canvas.
- [ ] Implement SSE token streaming chat with line buffering.
- **Acceptance Criteria:** Live streaming tokens render with instantaneous KaTeX.

### Phase 8: WebRTC Real-Time Voice Classroom
- [ ] Implement WebRTC audio transport and signaling in `app/adapters/voice/`.
- [ ] Integrate VAD and speech-to-text / text-to-speech pipelines.
- [ ] Implement speaking HUD indicators.
- **Acceptance Criteria:** Sub-700 ms roundtrip voice conversation.

### Phase 9: Mastery Tracking, Production & CI/CD Pipeline
- [ ] Implement `DatabaseEngine` with SQLite (local) and PostgreSQL support; Alembic migrations.
- [ ] Implement mastery calculation (Bayesian Knowledge Tracing / IRT); prerequisite gating.
- [ ] Persist transcripts, diagnostic histories, mastery trees.
- [ ] **Production Hardening**: Blue/green deploy; health checks; rollback; load testing
      (100 concurrent streaming sessions).
- [ ] **Observability Ops**: Langfuse alerts; cost/latency dashboards; eval regression gates.
- [ ] **Prompt Management**: Langfuse Prompt Hub versioning; A/B testing; template variables.
- **Acceptance Criteria:** CI green (from Phase 0.5); automated deploy succeeds; Langfuse
      dashboards operational; eval regression gates block bad releases.

---

## 3. Scope Discipline

| Class | Items |
|-------|-------|
| **NOW** | Phases 0, 0.5, 1–9 as prioritized by the roadmap |
| **SEAM** | LHS adapter (`export_version`/`schema_version`); voice provider (WebRTC ↔ text fallback); DB engine (SQLite→Postgres); distributed event bus (Redis/NATS LATER); **MCP transport** (stdio ↔ Streamable HTTP); **Memory backend** (ChromaDB ↔ Qdrant ↔ PGVector); **Checkpointer** (MemorySaver ↔ Postgres); **Local inference** (llama.cpp ↔ Ollama ↔ vLLM) |
| **LATER** | Multi-node scale-out, mobile native, multi-tenancy, payments, curriculum standards (CBSE/GCSE/NGSS/IB) |
| **OUT OF SCOPE** | Becoming a backend for any other repo; package-level coupling to JARVIS/LearningHubSTEM; speculative shared infrastructure; hosting multi-tenant SaaS |

---

## 4. Successor Parity Check (vs JARVIS)

| JARVIS capability | PROFESSOR-J status (reconciled 2026-08) |
|---|---|
| Cognitive Brain (Intent→Plan→Execute→Synthesize) | Foundation in `app/brain/` (Phase 3 foundation; agents/guard-rail wiring pending) |
| `@safety_gate` guardrails | **Implemented** in `app/guardrails/` (Phase 4/5 scaffold ahead of tool exposure) |
| Multi-provider routing + circuit breakers | Foundation in `app/models/` + `app/resources/` (Phase 2 foundation) |
| Hybrid memory | Planned (Phase 4) — not implemented |
| Session & workspace management | Planned (Phase 4) — not implemented |
| Tool sandbox | Planned (Phase 5) — not implemented |
| FastAPI + Next.js UI | Planned (Phase 7) — not implemented |

Every item above is ported from JARVIS patterns with an ADR, under this repo's governance.
Items marked "foundation" are implemented and unit-tested but do not yet satisfy the full phase
acceptance criteria (see the phase notes above); items marked "planned" are roadmap, not built.
