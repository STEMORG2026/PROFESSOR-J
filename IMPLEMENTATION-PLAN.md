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
- [x] **Memory Backend Abstraction**: `MemoryBackend` protocol + `ChromaMemoryBackend` impl (pluggable for Qdrant/PGVector).
- [x] **MCP Client Design** (Phase 1 deliverable): `MCPServerManager` interface, stdio + Streamable HTTP transports,
      `MCPToolSearch` for on-demand loading, `MCPRegistry` for caching.
- [x] Write unit tests: domain models (100%), LHS adapter (100% + zero-drift), prerequisite traversal,
      memory backend contract tests.
- **Acceptance Criteria:** 100% coverage for domain + adapters; MCP interfaces defined; memory backend swappable.

> Note (reconciled 2026-08): domain dataclasses, the LHS consumer adapter, the GeneralKnowledgeAdapter and
> their tests are merged on `main`. The memory backend and MCP client remain not-implemented (their contract
> work is scheduled within this phase's remaining scope). The contract version is `0.1` (both export and
> schema), as validated by `app/knowledge/lhs_adapter.py` — earlier references to version `3` were stale.
>
> Note (reconciled 2026-08-30): MemoryBackend protocol + InMemoryBackend, JsonMemoryBackend, ChromaMemoryBackend
> implemented with full test coverage. MCPServerManager, StdioTransport, StreamableHTTPTransport, MCPRegistry,
> MCPToolSearch implemented. All Virtual Board checks pass.

### Phase 2: Multi-Provider Model Pool & Circuit Breakers
- [x] **Provider Interface** (`app/models/providers.py`): `LLMProvider` (abstract), `LLMResult` (standardized),
      `complete`/stream signatures. Includes `MockProvider` (deterministic, tests/dev) and
      `OpenAICompatProvider` (any OpenAI-compatible `/chat/completions` endpoint).
- [x] **Provider Implementations**: Ported JARVIS's 17+ providers — `OllamaProvider`, `AnthropicProvider`,
      `GoogleProvider`, `OpenAICompatibleProvider` (covers OpenAI, OpenRouter, Groq, Together, NVIDIA NIM,
      GitHub Models, HF, Mistral, Cohere, Cerebras, Cloudflare, Zhipu, xAI via env-based registration).
- [x] **Live Provider Catalog** (`app/models/catalog.py`): Dynamic discovery of endpoints;
      curated defaults + runtime registration; no hardcoded fallbacks. `default_catalog()` auto-registers
      all providers with valid environment variables.
- [x] **Circuit Breakers** (`app/resources/circuit_breaker.py`): 3-state (`CLOSED`, `OPEN`,
      `HALF_OPEN`); `TokenBudget` TPM/RPM accounting; auto-failover on 429/503; configurable cooldown.
- [x] **ModelRouter** (`app/models/router.py`): provider selection → failover; integrates with
      `TokenBudget` + circuit breakers. Explicit `preferred` provider selection works; task-type
      classification → provider selection remains **SEAM** (future work).
- [x] **Bounded retry**: `bounded_retry()` (honors `retry_after`, jittered backoff) in
      `app/models/retry.py`; available for wiring into router's per-call path.
- [x] **Tests** (`tests/unit/models/`, `tests/unit/resources/`): fault injection (rate-limit,
      timeout, auth, circuit-open), failover, breaker state transitions, budget caps, retry backoff,
      plus 9 new tests for real provider implementations.
- **Acceptance Criteria:** Router switches to fallback provider on simulated rate limits;
      catalog refreshes without restart; all 17+ providers register and health-check.

> Note (reconciled 2026-08): the model-pool *foundation* (typed providers, catalog, circuit breakers,
> budgets, router failover, bounded retry) is implemented and unit-tested on `main`. The breadth of
> shipping all 17+ real provider integrations is now **COMPLETE** via `real_providers.py` +
> `register_all_providers()`. Per-provider health checks and task-type→provider routing remain
> as **SEAM** items for future work.

### Phase 3: Cognitive Engine (LangGraph) + Socratic Agents
- [x] **LangGraph Integration** (`app/brain/`): `StateGraph` (TypedDict `BrainState`) with nodes
      for intent classification → plan construction → synthesis, conditional flow.
      **Checkpointing (pause/resume) implemented via `MemorySaver`** (thread_id = learner
      id, `app/brain/tutorial.py`); streaming is implemented (SSE, PR #74).
- [x] **CognitiveBrain**: LangGraph node composition — intent classification → plan generation
      → synthesis via the model router, with SSE token streaming (PR #74). Guarded execution
      (safety gate) is future work.
- [x] **ProfessorAgent** (`app/brain/professor.py`): Tutoring modes (Socratic Mentor, Expository
      Lecture, Exam Drill, Research Advisor); rule-based misconception diagnosis (MisconceptionType
      catalog); prerequisite readiness gating; grounded-vs-ungrounded responses via LHS knowledge.
- [x] **EvaluatorAgent** (`app/brain/evaluator.py`): deterministic rubric evaluation (numeric
      tolerance + accepted-principle terms); diagnostic assessment; mastery tracking via
      `LearnerState`. SymPy step verification is Phase 5 work.
- [x] **ResearchAgent**: PDF ingestion → chunking → retrieval → cited synthesis
      (`app/knowledge/research.py` + `ingest.py`); exposed via `POST /api/ingest` (Phase 6).
      MCP external search integration is optional/future.
- [ ] **ToolExecutorAgent**: Sandbox dispatch; `@safety_gate` enforcement; MCP tool invocation
      via `MCPServerManager`; result synthesis.
- [x] **Simulated Student Test**: Newton's 2nd Law pass — agent guides without revealing answer
      (`tests/unit/brain/test_tutorial_loop.py`).
- **Acceptance Criteria:** LangGraph checkpointing works (pause/resume); simulated student
      passes Newton's 2nd Law; OTel spans emitted for each node.

> Note (reconciled 2026-08): a foundational `app/brain/` pipeline (rule-based intent classification →
> deterministic plan from the domain ExecutionPlan models → synthesis through the ModelRouter) is
> implemented and end-to-end tested against the deterministic MockProvider. The ProfessorAgent and
> EvaluatorAgent now drive a checkpointed Socratic tutoring loop verified by the simulated-student
> Newton's 2nd Law test. The Research/ToolExecutor agents, streaming, OTel per-node spans, and the
> SymPy step-verifier (Phase 5) are not yet done.

### Phase 4: Platform Parity — Session, Workspace, Memory, Tools
- [x] **SessionManager** (`app/session/`): per-learner durable, resumable sessions over the domain
      `Session`/`Conversation` models, with a pluggable `SessionStore` (in-memory + JSON-file). A
      session id is a valid LangGraph checkpoint `thread_id` (integrated with checkpointing).
      Port of JARVIS session patterns.
- [x] **WorkspaceManager** (`app/workspace/`): path-escape-safe, size-bounded file operations scoped
      to a learner workspace; dispatch via the tool executor (SAFE vs DESTRUCTIVE).
- [x] **Hybrid memory** (`app/memory/`): JARVIS-parity layer — rich `Memory` schema
      (category/type/behavior/confidence/importance/recency/frequency), durable `MemoryStore`,
      `MemoryManager` behavior lifecycle (append/replace/ignore/delete), keyword candidate
      retrieval + weighted `MemoryRanker` (relevance × importance × frequency × recency ×
      confidence), rule-based fact extraction, learner-namespaced `MemoryService`, and
      `ReflexionEngine` lessons. The original pluggable `MemoryBackend` seam (InMemory/Json/
      Chroma) remains intact.
      **Dense Chroma vector retrieval (BM25-sparse keyword is done; dense leg optional) and
      `SkillSynthesizer` are still pending.**
- [x] **ToolExecutor** (`app/tools/`): single safety choke point — tools register with a
      `SafetyTier` and every call is funneled through the safety policy (injection + PII + HITL for
      DESTRUCTIVE), failing closed on denial. `MCPToolExecutor` for MCP invocation is NOT yet done.
- [ ] Enable general-purpose chat/file/workspace assistance (non-education paths).
- [x] **MCP Integration Complete**: `MCPServerManager` management layer (stdio + Streamable
      HTTP) + `MCPToolSearch` on-demand + `CodeExecutionTools` (`app/mcp/manager|search|transports|registry`),
      wired into the composition root (`bootstrap.AppRoot.mcp`, dormant by default). The legacy
      stdio/SSE protocol client layer is restored as `app/mcp/client.py` (kept separate by design;
      final unification is a future architectural decision).
- **Acceptance Criteria:** ≥ 90% of JARVIS capabilities operational; MCP tools invokable
      from agents; checkpointing + Langfuse traces visible for all operations.

### Phase 5: Code & Math Sandbox Execution Engine
- [x] Implement `app/tools/sandbox.py` (foundation: isolated subprocess `-I`, wall-clock timeout
      watchdog that terminates infinite loops, RLIMIT_AS memory cap, no network env leakage).
      **Docker + gVisor isolation, cgroups CPU quotas, and PII redaction are the production
      hardening remaining (see note below).**
- [ ] **Local Inference**: Bundle `llama.cpp` (desktop); external Ollama server (server
      deployment); model quantization (Q4_K_M) for CPU-first UX.
- [x] Implement SymPy solver tool (`MathSolver`: algebra solve/simplify, calculus diff/integrate; unit
      conversions pending). Wired SAFE into the executor.
- [ ] Implement Plotly/Matplotlib chart generator tool.
- [x] Enforce `@safety_gate` tiers with HITL — `run_code` is DESTRUCTIVE (mandatory approval),
      `solve_math` SAFE; every DESTRUCTIVE call passes through the executor (audit-logged).
- **Acceptance Criteria:** Sandbox prevents harmful filesystem calls and terminates
      infinite loops cleanly; bundled llama.cpp runs on CPU; OTel spans for sandbox events.

> Note (reconciled 2026-08): the in-process subprocess sandbox is implemented and tested
> (timeout kills infinite loops, memory capped, isolated mode). Docker + gVisor containment,
> cgroups quota, real units solver, Plotly charts, and the llama.cpp/Ollama local-inference
> bundle require external infrastructure and remain TODO — do not mark the phase fully
> accepted until the Docker + llama.cpp criteria are genuinely met.

### Phase 6: Knowledge, Research & PDF Ingestion Pipeline
- [x] Implement `ResearchAgent` for academic paper processing (`app/knowledge/research.py`:
      extract -> chunk -> index -> cited synthesis; deterministic, ungrounded when no match).
- [x] **Ingestion API wiring**: `POST /api/ingest` accepts an uploaded PDF, runs extract →
      chunk → index through `ResearchAgent`, and returns the chunk count + source. The
      frontend routes PDF uploads through it. `POST /api/chat/upload` now ingests PDFs and
      injects page-exact retrieved chunks (with citations) into the prompt so the model can
      answer from the document.
- [~] Implement PDF text extraction (`app/knowledge/pdf.py` via PyMuPDF; page-level provenance).
      **Table/formula extraction and PaddleOCR for scanned PDFs are NOT yet done.**
- [ ] Set up `ChromaVectorStore` wrapper and BM25 retriever in `app/memory/` (Phase 4 `MemoryBackend`
      seam used in-process; dense/sparse backends pending).
- [~] Implement citation provenance mapper (page number + snippet; **bounding box pending**).
- **Acceptance Criteria:** Ingested paper is queryable with exact page-level citations
      (met for text-based PDFs; scanned-PDF OCR is external-infra TODO).

### Phase 7: Next.js 15 Interactive Canvas UI
- [x] Scaffold `frontend/` with Next.js 15 App Router, React 19, Tailwind (dark holographic chat
      canvas; FastAPI backend in `app/adapters/api.py`; enabled the CI `build-frontend` job).
      **A custom `@lobehub/ui` theme is NOT yet done; KaTeX + Plotly + SSE streaming ARE done.**
- [ ] Integrate `@lobehub/ui` dark holographic theme.
- [x] Implement KaTeX equation renderer and Plotly chart canvas (`MessageContent.tsx` parses
      `$...$` / `$$...$$` via `katex`, and ```` ```plotly {json} ``` ```` via `react-plotly.js`;
      `PlotlyChart.tsx` dynamic-imported for code-splitting).
- [x] Implement SSE token streaming chat with line buffering (FastAPI `StreamingResponse`
      SSE `text/event-stream`; provider + router + brain stream layers; frontend
      `ReadableStream`/`TextDecoder` SSE parser; `meta`/`token`/`done` events; abort via
      AbortController; node-level unit + API tests).
- **Acceptance Criteria:** Live streaming tokens render with instantaneous KaTeX
      (MET — tokens stream live, KaTeX equations and Plotly charts render interactively;
      only the `@lobehub/ui` cosmetic theme remains).

### Phase 8: WebRTC Real-Time Voice Classroom
- [ ] Implement WebRTC audio transport and signaling in `app/adapters/voice/`.
- [ ] Integrate VAD and speech-to-text / text-to-speech pipelines.
- [ ] Implement speaking HUD indicators.
- **Acceptance Criteria:** Sub-700 ms roundtrip voice conversation.

### Phase 9: Mastery Tracking, Production & CI/CD Pipeline
- [x] Implement `DatabaseEngine` with SQLite (local) — `app/db/`: engine + `MasteryRepository` +
      `TranscriptRepository`. **PostgreSQL support and Alembic migrations are NOT yet done
      (Postgres is the engine-URI SEAM).**
- [~] Implement mastery calculation (Bayesian Knowledge Tracking is the `MasteryScore.with_attempt`
      model; **IRT and full prerequisite-gate persistence are pending**).
- [~] Persist transcripts, diagnostic histories, mastery trees — transcripts + mastery persisted;
      **full diagnostic/mastery-tree model is pending**.
- [ ] **Production Hardening**: Blue/green deploy; health checks; rollback; load testing
      (100 concurrent streaming sessions).
- [ ] **Observability Ops**: Langfuse alerts; cost/latency dashboards; eval regression gates.
- [ ] **Prompt Management**: Langfuse Prompt Hub versioning; A/B testing; template variables.
- **Acceptance Criteria:** CI green (from Phase 0.5); automated deploy succeeds; Langfuse
      dashboards operational; eval regression gates block bad releases.

---

## 2b. Overall Implementation Status (honest, reconciled 2026-08)

**Implemented & tested in-process (suite green, mypy strict, board 8/8):**
- Phase 0, 0.5: governance, foundation hardening.
- Phase 1: domain dataclasses, LHS adapter + general-knowledge fallback.
- Phase 2 foundation: model pool (providers, catalog, circuit breakers, budgets, retry).
- Phase 3: LangGraph brain, ProfessorAgent (Socratic), EvaluatorAgent (rubric), MemorySaver
  checkpointed tutorial loop, simulated-student acceptance test. ResearchAgent/ToolExecutorAgent
  pending.
- Phase 4: SessionManager, WorkspaceManager, MemoryService + ReflexionEngine + JARVIS-parity
  hybrid-memory layer (rich schema, MemoryStore, MemoryManager lifecycle, keyword retrieval,
  weighted MemoryRanker, fact extraction), ToolExecutor (safety choke point), bootstrap
  `build_root()`. Dense vector + SkillSynthesizer pending.
- Phase 5 foundation: in-process CodeSandbox (timeout/memory-capped) + MathSolver (SymPy).
- Phase 6 foundation: PDF text extraction + chunk/index + page-exact citations.
- Phase 7 foundation: Next.js 15 chat canvas + FastAPI `/api/chat` + `/api/health` (verified end-to-end).
- Phase 7 streaming: FastAPI `/api/chat/stream` SSE token streaming (provider/router/brain stream
  layers + frontend `ReadableStream` parser; `meta`/`token`/`done` events).
- JARVIS-parity utility layer: typed `InMemoryAsyncBus` (passive telemetry), `ContextWindowManager`
  (pairs-based token trimming), and `PromptLoader` (externalized mtime-cached prompts), wired
  into the composition root.
- Phase 9a: SQLite DatabaseEngine + mastery/transcript persistence; AppRoot.health().

**Genuinely external-infra / not implemented (do NOT mark done with stubs):**
- Docker + gVisor sandbox containment, cgroups quotas (Phase 5 hardening).
- llama.cpp / Ollama local inference bundle and quantization (Phase 5).
- ChromaDB **dense** vector retrieval; Qdrant/PGVector (Phase 4/6) — sparse keyword retrieval is done, dense embeddings pending.
- PaddleOCR scanned-PDF OCR; table/formula extraction; bounding-box citations (Phase 6).
- PostgreSQL + Alembic migrations; distributed bus (Phase 9).
- FastAPI WebRTC signaling + auth; @lobehub theme (Phase 7 cosmetic only; KaTeX/Plotly/SSE done); WebRTC voice (Phase 8).
- Production hardening, Langfuse observability ops, prompt management, automated deploy (Phase 9b).

These items depend on external infrastructure, real-time transport, or deployment targets not
available in the in-process development environment, and remain explicitly TODO per the scope
rules. The CI pipeline, branch protection, and Dependabot auto-merge are fully operational.

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
