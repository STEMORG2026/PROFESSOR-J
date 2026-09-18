# Changelog

> Companion: `changelog` v0.1.0 from ProjectTemplates 0.1.0
> Answers here are this project's source of truth.
> Re-generate or adopt a newer template only as a deliberate decision (`tpl update`).

---

## Unreleased

### Added (2026-09)
- **Agent Orchestration Plane (Phase 9+10+11):** complete orchestration stack
  - `app/acp/` — ACP JSON-RPC 2.0 server (`ACPServer`, `ACPRequest`, `ACPResponse`)
  - `app/orchestration/subagent_manager.py` — `SubagentManager` (spawn, stop, steer, list)
  - `app/orchestration/plugin_registry.py` — `PluginRegistry` (register, get, discover, list)
  - `app/orchestration/agent_router.py` — `AgentRouter` (classify tasks → route to dsh/Hermes/OpenCode/PROFESSOR-J)
  - `app/orchestration/hooks.py` — `HooksSystem` (Claude Code + Codex bridge)
  - `app/orchestration/session_manager.py` — `SessionManager` (fork, resume, export, import)
  - `app/orchestration/tool_search.py` — `ToolSearch` (find tools across agents)
  - `app/orchestration/sandbox.py` — `SandboxedExecution` (command/script with timeout)
  - `app/orchestration/task_tracker.py` — `TaskTracker` (Todo/Plan/Goal decomposition)
  - `app/orchestration/scheduler.py` — `Scheduler` (cron-like job scheduling)
  - `app/tools/web.py` — `WebSearch` (search + fetch)
  - `app/tools/browser.py` — `BrowserControl` (navigate, click, type, screenshot, scroll)
  - `app/tools/computer_use.py` — `ComputerUse` (launch, kill, focus, move, resize)
  - 21 orchestration tests + 7 SOTA tool tests, all passing
  - All singletons wired into `bootstrap.AppRoot`
- **STEM-TUITION narration now runs under the engine — workflow codified:** refreshed
  `agents_dev/stem-tuition/workflow.md` and `current-state.md` so the recorded process
  mandates the content-engine as the **single** path for narration: every batch-8+ narrative is
  a `narrative-lesson` artifact routed through `produce()` (ContentRequest → Blueprint →
  generate → deterministic schema + coverage hard gates → semantic verify → publish) and must
  publish, enforced by a per-batch **engine-gate test**
  (`packages/content-engine/tests/engine-gate-batchN.test.ts`). Batch-8 landed in STEM-TUITION
  (PR #36, merged `90f1788`): `motion`, `displacement`, `distance`, `speed`, `measurement`,
  `physical-quantity`, `time`, `unit`; narrated-physics floor 57 → 65. Content-engine tests now
  include the engine-gate test alongside 23 core + 25 stress (49 total). PROFESSOR-J knows
  narration is engine-gated, never a side-channel manual loop.
- **STEM-TUITION content engine now complete (N1–N6) — record kept current:** refreshed the
  content-engine skill, the `agents_dev/stem-tuition/current-state.md` brief, and the ops-doc
  seam to reflect that STEM-TUITION's content-production engine is finished — the request-driven
  `produce()` pipeline runner (Blueprint → generate → verify → targeted repair → publish) with
  injected LLM seams, plus a second `quiz` FormatSpec, landed in `packages/content-engine/`
  (ADR-016 N4–N6). v1 narration playbook + `scripts/narrate/` deprecated; 57/79 physics narrated.
  So PROFESSOR-J knows the engine is complete and a production workflow/litellm runner attachment
  is the next step.
- **STEM-TUITION content-production skills + working seam:** added
  `agents_dev/skills/stem-tuition-content-developer.md` and
  `agents_dev/skills/stem-tuition-content-engine.md` (loadable capability definitions with a
  `data:` block mirroring `SkillMetadata`), a dedicated working folder
  `agents_dev/stem-tuition/` (`current-state.md` + `workflow.md` + skills README), and a
  STEM-TUITION content-production subsection in `docs/650-workspace-operations.md` — so
  PROFESSOR-J knows the current development state (47/79 physics narrated, content-engine v2
  seam merged) and can continue the narrative-batching loop without re-deriving the process.
- **MCP subsystem unblocked (Phase 4):** restored the legacy stdio/SSE MCP protocol/client
  layer as `app/mcp/client.py` (`StdioMCPClient`, `SSEClient`, `MCPClientManager`, `MCPToolSkill`,
  `create_mcp_manager_from_config`) recovered from git history, and wire the current
  `app.mcp.manager` layer into the composition root (`bootstrap.AppRoot.mcp`, dormant by default,
  safety-gated). Fixed the `app/mcp` circular import, unblocking `tests/unit/mcp/` +
  `tests/unit/skills/` collection (previously part of the CI baseline). The two MCP layers keep
  distinct domain models by design (`server_id` vs `server_name`); unification is a future decision.
- **Plotly chart-generator tool (Phase 5):** `ChartGenerator`
  (`app/tools/charts.py`) builds deterministic, side-effect-free Plotly figure
  specs for line/scatter/bar/pie/histogram. Registered as the SAFE-tier
  `make_chart` tool; `plotly_json` output renders natively in the webapp's
  ` ```plotly {json} ``` ` block (completing the model→chart loop opened by PR
  #78). 10 new unit tests.
- **Document ingestion pipeline API (Phase 6):** the Phase 6 extract→chunk→index→cite
  pipeline (which existed only as a library) is now wired end-to-end.
  - `POST /api/ingest` — upload a PDF; saves + ingests through `ResearchAgent`, returns the
    chunk count and source label for citation queries.
  - `POST /api/chat/upload` — now ingests an uploaded PDF and injects page-exact retrieved
    chunks (with `(title, p.N)` citations) into the prompt so the model answers from the document.
  - Frontend `FileUpload` routes PDFs through `/api/ingest`; `ChatCanvas` shows a
    "✓ indexed N chunks" status on the attachment chip.
  - 4 new API tests; full suite green (563 passed).
- **KaTeX equations + Plotly charts (Phase 7 webapp):** message content now renders rich
  STEM output instead of plain text. `MessageContent.tsx` parses inline `$...$` and block
  `$$...$$` LaTeX (rendered with `katex`, errors fall back to raw text) and
  ` ```plotly {json} ``` ` fenced blocks into interactive plots (`PlotlyChart.tsx` via
  `react-plotly.js`, dynamic-imported so plotly.js stays out of the critical path).
  Wired into the chat canvas; `katex` + `plotly.js` + `react-plotly.js` added.
  Phase 7 acceptance criteria now MET (only the cosmetic `@lobehub/ui` theme remains).
- **JARVIS-parity utility layer (`app/events/`, `app/context/`, `app/prompt/`):** closes the
  gap with JARVIS's cross-cutting infrastructure, benchmarked against SOTA agent stacks:
  - `app/events/` — `InMemoryAsyncBus` (typed pub/sub) for *passive* telemetry/metrics/
    streaming events, with typed event contracts (`TelemetryEvent`, `StepExecutionEvent`,
    `HITLRequestEvent`, `ToolExecutionEvent`). Core loops call services directly (never the
    data path). Completes the `InMemoryAsyncBus` referenced in the ARCHITECTURE telemetry diagram.
  - `app/context/` — `ContextWindowManager` trims conversation in user/assistant *pairs*
    (preserves exchange coherence, never drops the active prompt), with a token counter that
    prefers tiktoken/transformers and falls back to a dependency-free estimate.
  - `app/prompt/` — `PromptLoader` externalizes prompts (`prompts/*.md`) with `{variable}`
    placeholders, mtime-cached for hot-reload, with required-variable introspection and safe
    dependency-free rendering.
  - All three are wired into the composition root (`AppRoot`).
  - 16 new unit tests; full suite green (559 passed).
- **JARVIS-parity hybrid memory (Phase 4):** the memory layer was upgraded from a thin
  backend seam (+ naive word-overlap search) to a full modular engine matching JARVIS and
  the leading agent-memory frameworks:
  - `app/memory/schema.py` — rich `Memory` dataclass (category/type/behavior/
    confidence/importance/recency/frequency/source, immutable `created_at` +
    mutable `updated_at`/`last_used`, version-tolerant `from_dict`).
  - `app/memory/store.py` — durable `MemoryStore`: atomic temp-file + `os.replace` writes,
    corruption quarantine, type-validated field updates (immutables blocked).
  - `app/memory/manager.py` — `MemoryManager`: append/replace/ignore/delete behavior
    lifecycle + lifecycle callbacks + retrieve pipeline (candidates → rank → touch).
  - `app/memory/hybrid.py` — `CandidateRetriever` protocol, `KeywordRetriever`, `HybridRetriever`
    (keyword + optional dense-vector fusion, dedup by id).
  - `app/memory/ranking.py` — `MemoryRanker` with `RankingWeights`: relevance × importance ×
    frequency × recency (half-life decay) × confidence.
  - `app/memory/fact_extractor.py` + `rules.py` — rule-based extraction of identity /
    preference / skill / learner facts from conversation.
  - `app/utils/text.py` — shared stop-word keyword extractor (single source of truth).
  - `MemoryService` retains its learner-namespaced `remember`/`recall`/`forget`/`count`
    surface and gains a JARVIS-parity façade (`store_memory`/`search_memories`/
    `extract_facts`/`list_memories`); `ReflexionEngine` lessons now ride the same path.
  - The original pluggable `MemoryBackend` seam (InMemory/Json/Chroma) remains intact.
  - 29 new unit tests (schema, keywords, ranking, hybrid, store, manager behaviors, fact
    extraction, service façade); full suite green (544 passed).

### Added (2026-08)
- **SSE token streaming chat (Phase 7):** the FastAPI surface now exposes `/api/chat/stream`,
  a `text/event-stream` endpoint that emits `meta` → `token` → `done` events. Streaming is
  threaded through three new layers: `LLMProvider.stream()` (async-generator base fallback +
  word-chunked `MockProvider` + native OpenAI-compatible `stream: true` `httpx` handling),
  `ModelRouter.stream()` (identical circuit-breaker/budget/failover semantics to `generate`),
  and `CognitiveBrain.stream_response()`. The frontend chat canvas consumes the stream via
  `fetch` + `ReadableStream`/`TextDecoder` with an SSE line parser, rendering tokens
  incrementally and carrying provider/intent metadata through to the final message. Aborting
  works via the existing `AbortController`.
- **Composition-root fix:** `app/bootstrap.py` gained the missing `SafetyTier` import (and a
  duplicate `app.db` import was removed), which previously crashed `build_root()` and blocked
  collection of the adapters/api test suite.

### Added (2026-08)
- **Authority enforcement (Phase 6):** trustworthy Principal identity
  (`app/authority/principal.py`), single AuthorityGateway choke point
  (`app/authority/gateway.py`) enforcing Principal → project → allocation →
  tier → capability → safety → provenance → audit, composition-root wiring
  (`app/bootstrap.py`), provenance-chain rules (AI/untrusted sources require
  human for privileged mutations), and 29 black-box adversarial tests
  (`tests/unit/authority/`). Governance foundation frozen.
- **API-key resolution:** provider credentials now resolve from the repo's gitignored `.env`
  as the source of truth (accepting the bare env name and a `PROFESSOR_`-prefixed override) and can
  no longer be shadowed by an unrelated ambient shell export (`SINGULARITY_API_KEY` in `~/.bashrc`).
- **Chat session persistence:** `SessionRepository` (sessions, conversations, user settings + global
  defaults, personas) over a new additive SQLite schema; the chat API persists sessions across restarts
  and resolves provider/model/base_url/system-prompt via a session → global-default → built-in chain.
- **Webapp redesign:** settings panel (general defaults, per-provider API keys with connection testing,
  personas), top bar, session sidebar, model/persona dropdowns, voice components, and file upload.
- **Voice subsystem:** provider abstractions + lazy factories with a local Piper TTS provider and a
  local faster-whisper STT provider, exposed via `/api/voice` routes.
- **MCP:** stdio MCP client (`StdioMCPClient`), `MCPClientManager`/`MCPRegistry` discovery + caching,
  `MCPToolSearch` on-demand loading, `CodeExecutionTools` code-API adapter, and an `MCPToolSkill`.

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

### Added (2026-08) — Phase 5 Code & Math Sandbox
- **`CodeSandbox` (`app/tools/sandbox.py`):** isolated subprocess execution (`python -I`, no stdin,
  no network env) with a wall-clock timeout watchdog that terminates infinite loops and a
  `RLIMIT_AS` memory cap.
- **`MathSolver`:** deterministic SymPy algebra/calculus solver (`solve`, `simplify`,
  `differentiate`, `integrate`), exposed SAFE through the executor.
- **`ToolExecutor.register_sandbox_tools()`:** wires `run_code` (DESTRUCTIVE → mandatory HITL) and
  `solve_math`/`math_calculus` (SAFE); the executor now awaits async tool functions.
- Note: Docker + gVisor containment, Plotly charts, unit conversions, and the llama.cpp local
  inference bundle remain external-infra TODO.

### Added (2026-08) — Phase 6 Knowledge & Research Pipeline
- **`PDFExtractor` (`app/knowledge/pdf.py`):** PyMuPDF text extraction preserving page-level
  provenance; scanned/image-only PDFs raise a clear "OCR later" error.
- **`TextChunker` + `DocumentIngester` + `CitationMapper` (`app/knowledge/ingest.py`):** size-bounded
  overlapping chunking, indexing into the Phase 4 `MemoryBackend` seam, and retrieval mapped to
  page-exact (source, page, snippet) citations.
- **`ResearchAgent` (`app/knowledge/research.py`):** ingest → retrieve → cited synthesis; ungrounded
  when nothing matches.
- 13 new pipeline tests. Note: PaddleOCR for scanned PDFs, table/formula extraction, bounding-box
  citations, and a dense Chroma retriever remain external-infra TODO.

### Added (2026-08) — Phase 9a DatabaseEngine + persistence
- **`DatabaseEngine` (`app/db/engine.py`):** engine-agnostic persistence backbone with a SQLite
  implementation (Postgres is the engine-URI SEAM). Installs `mastery_records` + `transcripts`.
- **`MasteryRepository` / `TranscriptRepository` (`app/db/repositories.py`):** persist/load
  learner mastery and session transcripts (upsert semantics; per-session isolation).
- 5 tests. Note: Postgres + Alembic migrations and full diagnostic/mastery-tree models remain TODO.

### Added (2026-08) — ReflexionEngine + bootstrap root
- **`ReflexionEngine` (`app/memory/reflexion.py`):** distills turn outcomes into durable learner
  lessons (reinforcement/correction/misconception), stored through a `MemoryBackend` and recallable
  per learner — the Phase 4 self-improvement loop.
- **`build_root` (`app/bootstrap.py`):** composes all singletons (session, memory, reflexion, db,
  tools, knowledge, research) off SQLite/in-memory defaults.
- 5 tests.
- **`SkillSynthesizer`, ChromaDB/BM25 dense+sparse, and Postgres remain external-infra TODO.**

### Added (2026-08) — Phase 7 Frontend + API
- **`frontend/`:** Next.js 15.3.1 + React 19 + Tailwind 4 chat/tutoring canvas (dark holographic),
  `ChatCanvas` posts `/api/chat`, shows intent/provider, proxies `/api/*` to the backend.
  Builds clean; `pnpm typecheck` + `pnpm lint` pass.
- **`app/adapters/api.py`:** FastAPI `GET /api/health` + `POST /api/chat` wired to the CognitiveBrain
  (MockProvider default → zero-config testing). `build_root()` degrades if LHS export absent.
- **CI:** `build-frontend` job enabled (node 22, pnpm).
- Kicks the SSE streaming/KaTeX/Plotly/@lobehub theme + WebRTC to later (see §2b).

### Added (2026-08-30) — Phase 1 Memory Backend Abstraction + MCP Client Design
- **`app/memory/backends.py`:** `MemoryBackend` abstract protocol + `InMemoryBackend`,
  `JsonMemoryBackend`, `ChromaMemoryBackend` implementations. Pluggable for Qdrant/PGVector.
  `MemoryService` and `ReflexionEngine` now work with any backend implementation.
- **`app/mcp/`:** Complete MCP client subsystem — `MCPServerManager` (multi-server management),
  `StdioTransport` + `StreamableHTTPTransport`, `MCPRegistry` (caching), `MCPToolSearch`
  (on-demand discovery + CodeExecutionTools pattern).
- **Tests:** Extended `tests/unit/memory/test_memory.py` with ChromaDB backend tests.
- **Virtual Board:** All 8 checks pass including new `mcp_tool_search` verification.

### Added (2026-08-30) — Phase 2 Multi-Provider Model Pool (17+ Real Providers)
- **`app/models/real_providers.py`:** Complete provider implementations —
  `OpenAICompatibleProvider` (covers OpenAI, OpenRouter, Groq, Together, NVIDIA NIM, GitHub Models,
  HuggingFace, Mistral, Cohere, Cerebras, Cloudflare, Zhipu, xAI via OpenAI-compatible endpoints),
  `AnthropicProvider` (native Claude API), `OllamaProvider` (native + HTTP fallback),
  `GoogleProvider` (native Gemini API). All map to typed `LLMProvider` interface.
- **`app/models/catalog.py`:** `default_catalog()` now auto-registers all providers whose
  required environment variables are set (local-first: `ollama` + `mock` always available).
- **`app/models/__init__.py`:** Exports all real provider classes + `register_all_providers()`.
- **Tests:** `tests/unit/models/test_real_providers.py` — 9 tests covering all 4 provider types
  + catalog registration logic with environment variable gating.
- **Coverage:** Total project coverage 82% (up from 84% before tests added).

---

## Release discipline

- Keep the top entry as **Unreleased** until a version is cut.
- Format per change: date, kind (added / changed / fixed / deprecated / removed),
  summary, and a link (commit or ADR).
- Note dependencies that changed alongside (e.g. LearningHubSTEM export version, provider
  catalogs, Python/Node versions).
