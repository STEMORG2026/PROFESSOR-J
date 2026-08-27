# Architecture

> Companion: `architecture` v0.1.0 from ProjectTemplates 0.1.0
> Answers here are this project's source of truth.
> Re-generate or adopt a newer template only as a deliberate decision (`tpl update`).

---

## Decomposition (main components and responsibilities)

Status convention: **IMPLEMENTED** (merged on `main`, unit-tested) · **scaffold** (partial/foundation
present) · **planned** (roadmap, not built).

| Component | Responsibility | Status (2026-08) |
|-----------|----------------|------------------|
| `frontend/` | Next.js 15 canvas & voice UI; render-only, no business logic | planned |
| `app/adapters/` | FastAPI REST, SSE, WebSocket/WebRTC signaling; Bearer auth | planned |
| `app/bootstrap.py` | Composition root — DI wiring of all singletons | planned |
| `app/brain/` | CognitiveBrain (intent→plan→synthesize) via LangGraph; Professor/Research/Evaluator/ToolExecutor agents | scaffold (`app/brain/`: intent→plan→synthesize pipeline is implemented; agents not built) |
| `app/guardrails/` | `@safety_gate` tiers (SAFE/SENSITIVE/DESTRUCTIVE→HITL) + prompt-injection + PII | **IMPLEMENTED** |
| `app/knowledge/` | LearningHubSTEM consumer adapter + general-knowledge fallback | **IMPLEMENTED** |
| `app/memory/` | Hybrid ChromaDB + BM25 retrieval | planned |
| `app/db/` | Learner mastery, transcripts, diagnostic history (SQLite → Postgres) | planned |
| `app/session/` | Per-user session state | planned |
| `app/workspace/` | File/workspace operations under safety policy | planned |
| `app/tools/` | Sandboxed tool execution (Python, SymPy, Plotly, graph queries) | planned |
| `app/models/`, `app/resources/` | Multi-provider router + circuit breakers + token budgets + bounded retry | scaffold (`app/models/` + `app/resources/` foundation implemented; 17+ real providers & task-type routing pending) |
| `app/skills/` | Skill registry + built-ins (filesystem, git, web_search, code_execution, LHS knowledge, memory) | **IMPLEMENTED** (web_search/code_execution/memory signal `not_implemented` until their backends exist) |
| `app/config/`, `app/exceptions.py`, `app/logging_config.py`, `app/telemetry/` | Settings, typed exception taxonomy, JSON logging, OTel exporter | **IMPLEMENTED** |
| `app/events/` | Passive async bus | planned |

## Boundaries and interfaces

- Presentation → adapters → bootstrap → brain → domain (one direction only).
- External integration (LearningHubSTEM, providers) via adapters/contracts; never at the
  package level.
- Public interfaces (REST/SSE/WS) are versioned (`/api/v1/...`).

## Data and control flows

1. User → frontend → adapter → brain (intent classification → plan → guarded execution →
   synthesis).
2. Grounded context flows from LearningHubSTEM adapter into the prompt.
3. Provider failover on 429/503 via circuit breakers.
4. Telemetry events flow passively to the bus.

## What varies over time vs what stays stable

- **Stable:** domain model, safety tiers, layer boundaries, LearningHubSTEM contract.
- **Varies:** providers/catalogs, frontend presentation, voice backends, storage engine
  (SQLite→Postgres), event-bus backend (Redis/NATS LATER).

## Key structural decisions, each traced to a constraint/principle

- Clean layering → principles 2 (teach), 7 (increments); constitution N1 (grounding).
- Multi-agent brain → principles 1-2; architecture invariant 4 (sandbox).
- Circuit breakers → principle 4 (resilience).
- Consumer adapter → workspace invariant (independent peers, contract integration).
