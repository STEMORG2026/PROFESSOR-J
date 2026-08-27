# PROFESSOR-J — System Architecture

> **Architecture Style:** Clean Layered Architecture + **LangGraph Orchestration Runtime** +
> Multi-Agent Cognitive Engine (JARVIS patterns adapted)
> **Status:** Living Architecture at Inception
> **Version:** 0.1.0

> **⏱ IMPLEMENTATION STATUS (reconciled 2026-08):** this file is the *target* architecture.
> What is actually implemented on `main` today is the **foundation** — the domain layer, LHS
> knowledge adapter, skills system, guardrails/safety gate, model pool, and a minimal LangGraph
> brain pipeline are built and unit-tested (see `docs/300-architecture.md` for the per-layer
> status, and `IMPLEMENTATION-PLAN.md` for what remains). The layers drawn here as if live
> (`frontend/`, adapters, bootstrap, memory, db, session, workspace, tools, MCP client, agents)
> are **planned**, not yet built. Read `docs/300-architecture.md` for the accurate current state.

---

## 1. Platform positioning

PROFESSOR-J is a **general-purpose autonomous AI platform** (an AI OS) that inherits the
proven architectural foundations of **JARVIS** under a new name and generalizes them.
It is **not bound to LearningHubSTEM**. It consumes LearningHubSTEM as one specialized
knowledge source among others via a consumer adapter, and falls back to general knowledge
where no canonical entity exists.

| JARVIS capability | PROFESSOR-J status |
|---|---|
| Cognitive Brain (Intent→Plan→Execute→Synthesize) | **Inherited, upgraded** with Professor/Research/Evaluator agents |
| `@safety_gate` tiered guardrails | **Inherited** |
| Multi-provider model pool + circuit breakers | **Inherited** |
| Hybrid memory (ChromaDB + BM25) | **Inherited** |
| Session & workspace management | **Inherited** |
| Tool sandbox | **Inherited** |
| FastAPI + Next.js UI | **Inherited** |
| Socratic tutoring, research, pedagogy | **New** (primary domain) |

**Ratified Architecture Decisions (Infrastructure Audit §6):**

| Decision | Choice | Phase |
|---|---|---|
| Orchestration Runtime | **LangGraph** — graph-based, checkpointing, interrupts, OTel | 0.5 |
| Observability | **Self-host Langfuse** — prompt mgmt, datasets, evals, OTel | 0.5 |
| MCP Integration | **Phase 1 design** — stdio + Streamable HTTP, tool search, code-as-tools | 1 |
| Local Inference | **Bundle llama.cpp** (desktop); **External Ollama** (server) | 5 |
| Provider Catalog | **Curated defaults + dynamic discovery** | 2 |
| Memory Backend | **Abstract interface + ChromaDB impl** (pluggable) | 1 |
| Frontend | **Next.js 15 web** (per PRD); desktop wraps later | 7 |

Integration with JARVIS is **pattern-level only**: PROFESSOR-J never couples to JARVIS at
the package level. Ported code is adapted under this repository's governance and recorded
in `docs/adr/`.

---

## 2. System Topology & Layering

```mermaid
graph TD
    Client[Next.js 15 Canvas & Voice UI] -->|HTTP / SSE / WSS / WebRTC| Adapters[app/adapters/ Layer]
    Adapters -->|Token Auth & Validation| Bootstrap[app/bootstrap.py Composition Root]
    Bootstrap -->|Dependency Injection| Brain[app/brain/ Multi-Agent Cognitive Engine]

    subgraph Orchestration ["LangGraph Orchestration Runtime"]
        Brain -->|StateGraph| LangGraph[LangGraph Pregel Runtime<br/>Checkpointing · Interrupts · Streaming]
    end

    subgraph CognitiveEngine ["Cognitive Engine (app/brain/)"]
        Cognitive[CognitiveBrain<br/>IntentAnalyzer · TaskPlanner ·<br/>ExecutionRunner · ResponseSynthesizer]
        Professor[ProfessorAgent<br/>Pedagogical & Socratic Orchestrator]
        Research[ResearchAgent<br/>Literature & Document Synthesis]
        Evaluator[EvaluatorAgent<br/>Proof & Diagnostic Verifier]
        ToolAgent[ToolExecutorAgent<br/>Sandbox & Code Runner]
    end

    Brain --> Cognitive
    Cognitive --> Professor
    Professor --> Research
    Professor --> Evaluator
    Professor --> ToolAgent

    subgraph Guardrails ["Safety Policy & Guardrails (app/guardrails/)"]
        SafetyGate["@safety_gate<br/>SAFE / SENSITIVE / DESTRUCTIVE"]
        InjectionGuard[PromptInjectionDetector]
        PIIGuard[PII Redactor]
    end

    ToolAgent --> SafetyGate
    SafetyGate --> InjectionGuard
    InjectionGuard --> PIIGuard

    subgraph Foundations ["Knowledge & Memory Layer"]
        LHSAdapter[LHSKnowledgeAdapter<br/>LearningHubSTEM Consumer Seam]
        GenKnowledge[GeneralKnowledgeAdapter<br/>Ungrounded fallback]
        VectorStore[ChromaVectorStore<br/>Semantic Embeddings]
        Memory[MemoryService<br/>Dense + BM25 hybrid]
        LearnerDB[DatabaseEngine<br/>PostgreSQL / SQLite Mastery Store]
    end

    Professor --> LHSAdapter
    LHSAdapter --> GenKnowledge
    Research --> VectorStore
    Cognitive --> Memory
    Evaluator --> LearnerDB

    subgraph ModelPool ["Multi-Provider LLM Pool (app/models/, app/resources/)"]
        Router[ModelRouter]
        CircuitBreaker[ResourceManager & 3-State Breakers]
        Catalog[Live Provider Catalog<br/>Curated Defaults + Dynamic Discovery]
    end

    Brain --> Router
    Router --> CircuitBreaker
    Router --> Catalog

    subgraph PlatformServices ["Platform Services (from JARVIS)"]
        Session[SessionManager<br/>Per-user session state]
        Workspace[WorkspaceManager<br/>File & workspace ops]
        Tools[ToolExecutor<br/>Sandbox, SymPy, Plotly, graph queries]
    end

    Brain --> Session
    Brain --> Workspace
    ToolAgent --> Tools

    subgraph MCPIntegration ["MCP Client (Phase 1)"]
        MCPManager[MCPServerManager<br/>stdio + Streamable HTTP]
        ToolSearch[MCP Tool Search<br/>On-demand loading]
        CodeExec[Code-as-Tools Pattern<br/>Filesystem code APIs]
    end

    ToolAgent --> MCPManager
    MCPManager --> ToolSearch
    MCPManager --> CodeExec

    subgraph Observability ["Observability (Langfuse + OTel)"]
        OTel[OpenTelemetry SDK<br/>Spans: agent, tool, retrieval, guardrail, evaluator]
        Langfuse[Langfuse Self-Hosted<br/>Prompt Hub · Datasets · Evals · Traces]
    end

    Brain -.->|OTel Spans| OTel
    OTel -.->|Export| Langfuse
    Tools -.->|OTel Spans| OTel
    MCPManager -.->|OTel Spans| OTel

    subgraph PassiveTelemetry ["Passive Telemetry (app/events/, app/telemetry/)"]
        Bus[InMemoryAsyncBus]
        Tracer[Tracer & MetricCollector]
    end

    Brain -->|Telemetry Events| Bus
    Bus --> Tracer
```

---

## 3. Layer Definitions & Boundary Rules

### 3.1. Presentation Layer (`frontend/`)
- **Technology:** Next.js 15 (App Router), React 19, TypeScript (Strict), Tailwind CSS,
  KaTeX, Plotly/D3, WebRTC Media Stream Client.
- **Role:** Interactive whiteboard, streaming token rendering, voice lecturing HUD,
  diagnostic problem canvas, general chat UI.
- **Rule:** Zero business or pedagogical logic; communicates strictly via REST, SSE, and
  WebSocket endpoints.

### 3.2. Adapters & Transport Layer (`app/adapters/`)
- **Technology:** FastAPI, Uvicorn, WebSockets, WebRTC signaling.
- **Role:** Protocol serialization, Bearer token authentication (`PROFESSOR_API_KEY`),
  SSE stream line buffering, request dispatching.
- **Rule:** Adapters translate external protocols into pure domain calls.

### 3.3. Composition Root (`app/bootstrap.py`)
- `ApplicationContainer` wires all singletons and dependencies; the only place DI wiring
  lives.

### 3.4. Multi-Agent Cognitive Engine (`app/brain/`)
- **`CognitiveBrain`:** The intent→plan→execute→synthesize loop inherited from JARVIS;
  classifies prompts (`DIRECT_CHAT`, `FILE_QUERY`, `TOOL_SEARCH`, `MULTI_STEP`,
  `TUTORIAL`), generates execution plans, runs steps under safety policy, synthesizes
  responses.
- **`ProfessorAgent`:** The tutoring orchestrator. Analyzes student responses, chooses
  pedagogical strategy, coordinates subagents.
- **`ResearchAgent`:** Deep semantic search across ingested papers, formula extraction,
  cited summaries.
- **`EvaluatorAgent`:** Verifies student math steps (SymPy) and assesses code against test
  cases.
- **`ToolExecutorAgent`:** Executes sandboxed tools (Python, SymPy, Plotly, knowledge-graph
  queries).
- **Execution Model:** Direct `async/await` calls for zero-latency execution.

### 3.5. Knowledge & Memory Layer (`app/knowledge/`, `app/memory/`, `app/db/`)
- **`LHSKnowledgeAdapter`:** Consumes `LearningHubSTEM/exports/knowledge.json` for
  canonical definitions, prerequisite trees, equations.
- **`GeneralKnowledgeAdapter`:** Handles non-grounded topics; responses clearly labeled
  ungrounded.
- **`MemoryService`:** Hybrid ChromaDB dense + BM25 sparse retrieval.
- **`DatabaseEngine`:** Learner profiles, transcripts, diagnostic scores, mastery levels in
  SQLite (local) / PostgreSQL (production).

### 3.6. Platform Services (`app/session/`, `app/workspace/`, `app/tools/`)
- **`SessionManager`:** Per-user session state and context continuity.
- **`WorkspaceManager`:** File/workspace operations guarded by safety tiers.
- **`ToolExecutor`:** Sandboxed execution (subprocess, resource caps, timeout watchdog).

### 3.7. Model Routing & Resilience Layer (`app/models/`, `app/resources/`)
- **`ModelRouter`:** Multi-provider load balancer across local and cloud LLM providers.
- **`ResourceManager`:** Tracks TPM/RPM budgets and 3-state circuit breakers
  (`CLOSED`, `OPEN`, `HALF_OPEN`) for automatic failover on 429/503.
- **`ProviderCatalog`:** Live dynamic discovery of available endpoints; curated defaults
  for UX (Ollama, OpenAI, Anthropic, Google, Groq, Cerebras, OpenRouter, etc.);
  no hardcoded fallbacks.

### 3.8. Safety & Guardrails Layer (`app/guardrails/`)
- **`@safety_gate`:**
  - `SAFE`: read-only (concept lookup, LaTeX) → auto-approved.
  - `SENSITIVE`: file parsing, web search → policy verified.
  - `DESTRUCTIVE`: code sandbox, file modification, DB resets → mandatory HITL approval.
- **`PromptInjectionDetector`:** Heuristic + embedding-based detection on all string args.
- **`PIIRedactor`:** Tokenization of sensitive data before model context; detokenization on return.

### 3.9. MCP Client Layer (`app/mcp/`) — Phase 1
- **`MCPServerManager`:** Manages stdio and Streamable HTTP transports; connection pooling;
  health checks; automatic reconnection.
- **`MCPToolSearch`:** On-demand tool definition loading; reduces context by 98%+ (Anthropic pattern).
- **`CodeExecutionTools`:** Presents MCP tools as filesystem code APIs; agent writes Python
  to invoke tools; PII stays in execution environment.
- **`MCPRegistry`:** Tool discovery + caching (`cache_tools_list`); filters per agent/run.

### 3.10. Observability Layer (`app/telemetry/`) — Phase 0.5
- **`OTelInstrumentation`:** OpenTelemetry SDK with semantic conventions (OpenInference):
  spans for `agent`, `tool`, `retrieval`, `guardrail`, `evaluator`, `embedding`, `prompt`.
- **`LangfuseExporter`:** OTLP export to self-hosted Langfuse; Prompt Hub, Datasets, Evals.
- **`Tracer` / `MetricsCollector` / `EventLogger`:** Structured telemetry with correlation IDs.

---

## 4. Data & Request Flow

```mermaid
sequenceDiagram
    autonumber
    actor Learner as Student / Researcher / User
    participant Client as Next.js 15 UI
    participant Adapters as FastAPI / WS Adapter
    participant Brain as CognitiveBrain / ProfessorAgent
    participant LHS as LHSKnowledgeAdapter
    participant Evaluator as EvaluatorAgent
    participant Router as ModelRouter (LLM Pool)
    participant Bus as InMemoryAsyncBus

    Learner->>Client: "How do I calculate acceleration from Newton's 2nd law?"
    Client->>Adapters: POST /api/chat/stream (Bearer Token)
    Adapters->>Brain: Orchestrate Turn (intent classification)
    Brain->>LHS: Lookup "lhs:phys.newtons-second-law"
    LHS-->>Brain: Canonical Equation: F = m·a, Prerequisites: [mass, force]
    Brain->>Evaluator: Check Learner Mastery for Prerequisites
    Evaluator-->>Brain: Mastery: [mass: 100%, force: 90%] → Ready for Socratic Hint
    Brain->>Router: Generate Socratic Prompt with Grounded Context
    Router-->>Adapters: SSE Token Stream (Chunks)
    Adapters-->>Client: Stream KaTeX & Dialogue Chunk
    Client-->>Learner: Display interactive formula & Socratic question
    Brain->>Bus: Publish TokenMetrics & StepExecutionEvent
```

---

## 5. Architectural Invariants (Non-Negotiable)

1. **Grounded Over Generative:** Factual STEM claims link to canonical LearningHubSTEM IDs;
   non-grounded responses are labeled ungrounded.
2. **Zero Monolithic Dependencies:** `app/domain/` is pure Python 3.11+ dataclasses with
   zero framework dependencies.
3. **Failover Resilience:** No single LLM provider outage can take down a session.
4. **Sandboxed Code Execution:** Code never runs in the host web-server process; it runs in
   an isolated, resource-capped subprocess behind `@safety_gate`.
5. **Independent Peer:** PROFESSOR-J never couples to JARVIS or LearningHubSTEM at the
   package level; integration is via contracts/adapters.
6. **General by Default:** The platform must remain capable of general assistance; education
   and research are primary domains, not exclusive.
