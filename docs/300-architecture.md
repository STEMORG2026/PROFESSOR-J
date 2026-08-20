# Architecture

> Companion: `architecture` v0.1.0 from ProjectTemplates 0.1.0
> Answers here are this project's source of truth.
> Re-generate or adopt a newer template only as a deliberate decision (`tpl update`).

---

## Decomposition (main components and responsibilities)

| Component | Responsibility |
|-----------|----------------|
| `frontend/` | Next.js 15 canvas & voice UI; render-only, no business logic |
| `app/adapters/` | FastAPI REST, SSE, WebSocket/WebRTC signaling; Bearer auth |
| `app/bootstrap.py` | Composition root — DI wiring of all singletons |
| `app/brain/` | CognitiveBrain (intent→plan→execute→synthesize) + ProfessorAgent, ResearchAgent, EvaluatorAgent, ToolExecutorAgent |
| `app/guardrails/` | `@safety_gate` tiers + prompt-injection detection |
| `app/knowledge/` | LearningHubSTEM consumer adapter + general-knowledge fallback |
| `app/memory/` | Hybrid ChromaDB + BM25 retrieval |
| `app/db/` | Learner mastery, transcripts, diagnostic history (SQLite → Postgres) |
| `app/session/` | Per-user session state |
| `app/workspace/` | File/workspace operations under safety policy |
| `app/tools/` | Sandboxed tool execution (Python, SymPy, Plotly, graph queries) |
| `app/models/`, `app/resources/` | Multi-provider router + circuit breakers |
| `app/events/`, `app/telemetry/` | Passive async bus, logging, metrics |

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
