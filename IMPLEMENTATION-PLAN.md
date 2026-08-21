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
- [ ] **Pydantic Settings** (`app/config/settings.py`): `BaseSettings` with validation, `.env.example`, secret detection at startup.
- [ ] **Structured Logging** (`app/logging_config.py`): JSON output, correlation IDs, log levels, OTel-ready.
- [ ] **Error Taxonomy** (`app/exceptions.py`): Typed exceptions, retry policies, circuit breaker hooks.
- [ ] **GitHub Actions CI** (`.github/workflows/ci.yml`): pytest, mypy strict, pre-commit, coverage gates, artifact upload.
- [ ] **ADR Infrastructure**: Create `docs/adr/`, MADR template, write ADR-001 (successor decision), ADR-002 (pattern inheritance), ADR-003 (layered architecture + LangGraph).
- [ ] **Secrets Validation**: Pre-commit + startup check for required env vars; fail fast on missing secrets.
- [ ] **Makefile**: Common targets (`make test`, `make typecheck`, `make lint`, `make run`, `make eval`).
- [ ] **Langfuse Self-Host** (docker-compose): Postgres + ClickHouse + Langfuse; OTel exporter config in `app/telemetry/exporter.py`.
- [ ] **OTel Instrumentation**: OpenTelemetry SDK + semantic conventions (agent, tool, retrieval, guardrail, evaluator spans).
- **Acceptance Criteria:** `make test` / `make typecheck` / `make lint` all pass; CI green on push; ADRs rendered; Langfuse UI accessible; OTel spans visible in Langfuse.

### Phase 1: Core Domain Models & LearningHubSTEM Consumer Seam
- [ ] Author pure Python dataclasses in `app/domain/` (`LearnerState`,
      `PedagogicalTurn`, `MisconceptionState`, `ConceptEntity`, `ExecutionPlan`,
      `ToolCallRequest`, `Session`, `Conversation`, `MasteryScore`).
- [ ] Implement `app/knowledge/lhs_adapter.py` reading
      `LearningHubSTEM/exports/knowledge.json`; validate `export_version`/`schema_version` (currently 3);
      prerequisite mapping from `mathematically_requires`/`logically_requires` relationship types.
- [ ] Implement `GeneralKnowledgeAdapter` fallback (labeled ungrounded with source provenance).
- [ ] **Memory Backend Abstraction**: `MemoryBackend` protocol + `ChromaMemoryBackend` impl (pluggable for Qdrant/PGVector).
- [ ] **MCP Client Design** (Phase 1 deliverable): `MCPServerManager` interface, stdio + Streamable HTTP transports,
      `MCPToolSearch` for on-demand loading, `MCPRegistry` for caching.
- [ ] Write unit tests: domain models (100%), LHS adapter (100% + zero-drift), prerequisite traversal,
      memory backend contract tests.
- **Acceptance Criteria:** 100% coverage for domain + adapters; MCP interfaces defined; memory backend swappable.

### Phase 2: Multi-Provider Model Pool & Circuit Breakers
- [ ] **Provider Interface**: `BaseLLMProvider` (abstract), `LLMResponse` (standardized),
      `generate_text`/`stream_text` signatures.
- [ ] **Provider Implementations**: Port JARVIS's 17+ providers (Ollama, llama.cpp, OpenAI,
      Anthropic, Google, Groq, Cerebras, OpenRouter, Mistral, Cohere, Together, NVIDIA NIM,
      GitHub Models, HF, Cloudflare, Zhipu, xAI, etc.).
- [ ] **Live Provider Catalog** (`app/models/catalog.py`): Dynamic discovery of endpoints;
      curated defaults for UX (Ollama, OpenAI, Anthropic, Google, Groq, Cerebras, OpenRouter);
      no hardcoded fallbacks; health endpoints per provider.
- [ ] **Circuit Breakers** (`app/resources/circuit_breaker.py`): 3-state (`CLOSED`, `OPEN`,
      `HALF_OPEN`); TPM/RPM budgets; auto-failover on 429/503; configurable cooldown.
- [ ] **ModelRouter** (`app/models/router.py`): Task-type classification → provider selection
      → failover; integrates with `ResourceManager` health checks.
- [ ] **Tests**: Fault injection — kill provider → verify failover <200ms; rate limit simulation;
      catalog refresh; circuit breaker state transitions.
- **Acceptance Criteria:** Router switches to fallback provider on simulated rate limits;
      catalog refreshes without restart; all 17+ providers register and health-check.

### Phase 3: Cognitive Engine (LangGraph) + Socratic Agents
- [ ] **LangGraph Integration**: `StateGraph` definition with `CognitiveState` (TypedDict);
      nodes for IntentAnalyzer, TaskPlanner, ExecutionRunner, ResponseSynthesizer;
      conditional edges for routing; checkpointing via `MemorySaver` → Postgres checkpointer.
- [ ] **CognitiveBrain**: LangGraph node composition — intent classification → plan generation
      → guarded execution → synthesis; streaming via `stream_mode="values"`.
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

- [x] Cognitive Brain (Intent→Plan→Execute→Synthesize) — Phase 3
- [x] `@safety_gate` guardrails — Phase 4/5
- [x] Multi-provider routing + circuit breakers — Phase 2
- [x] Hybrid memory — Phase 4
- [x] Session & workspace management — Phase 4
- [x] Tool sandbox — Phase 5
- [x] FastAPI + Next.js UI — Phase 7

Every item above is ported from JARVIS patterns with an ADR, under this repo's governance.
