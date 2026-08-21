# ADR-003: Clean Layered Architecture + LangGraph Orchestration Runtime

- **Status**: accepted
- **Date**: 2026-08-21
- **Version**: 0.1.0
- **Commit**: eff694e
- **Decider**: Sajan (Principal Architect)

## Context

PROFESSOR-J needs an orchestration runtime for its multi-agent cognitive engine.
Options considered:
1. **Custom direct-async loop** (JARVIS approach) — `IntentAnalyzer → TaskPlanner → ExecutionRunner → ResponseSynthesizer` via direct `await` calls
2. **LangGraph** — Graph-based state machine with checkpointing, interrupts, streaming, OTel
3. **Microsoft Agent Framework** — Graph workflows, middleware, OTel, .NET + Python
3. **Custom raw loop** — Minimal abstraction, full control

Key requirements from architecture:
- Explicit state management for long-running agent sessions
- Human-in-the-loop (HITL) interrupts for DESTRUCTIVE tool calls
- Checkpointing for pause/resume/recovery
- OTel observability (spans for agent, tool, retrieval, guardrail, evaluator)
- Parallel execution where possible
- Deterministic execution model
- Streaming token output

## Decision

We adopt **LangGraph** as the orchestration runtime for PROFESSOR-J's cognitive engine.

Architecture:
- **LangGraph Pregel runtime** executes `StateGraph` with `Pregel` algorithm (BSP)
- **Nodes** = CognitiveBrain components (IntentAnalyzer, TaskPlanner, ExecutionRunner, ResponseSynthesizer, ProfessorAgent, ResearchAgent, EvaluatorAgent, ToolExecutorAgent)
- **Edges** = Control flow (deterministic + conditional for routing)
- **State** = `CognitiveState` (TypedDict) — single source of truth
- **Checkpointing** = `MemorySaver` (dev) → `PostgresCheckpointer` (prod) via `langgraph-checkpoint-postgres`
- **Interrupts** = `interrupt()` for HITL on DESTRUCTIVE tools; `Command(resume=...)` for resume
- **Streaming** = `stream_mode="values"` for token streaming; `stream_mode="updates"` for node updates
- **OTel** = OpenTelemetry SDK with semantic conventions; export to Langfuse via OTLP HTTP

The JARVIS direct-async cognitive loop is **refactored into LangGraph nodes** — the
Intent→Plan→Execute→Synthesize logic moves into node functions, preserving the
pedagogical orchestration while gaining LangGraph's production features.

## Consequences

### Positive

- Production-grade checkpointing, interrupts, streaming out of the box
- Explicit state schema (`CognitiveState` TypedDict) — single source of truth
- OTel instrumentation built-in; Langfuse integration via OTLP
- Checkpointing enables pause/resume, time-travel debugging, HITL
- Deterministic Pregel execution — no race conditions
- Parallel node execution where DAG allows
- Industry standard — used by Klarna, Replit, Uber, Elastic
- Migration path from JARVIS: each cognitive component becomes a node

### Negative

- Learning curve for graph concepts (nodes, edges, state, checkpointing)
- More boilerplate than direct-async for simple flows
- LangGraph version pinning required (API stability through v2.0)
- Additional dependency (LangGraph + checkpointer)

### Neutral

- JARVIS direct-async pattern becomes "legacy" — documented in ADR-002
- Cognitive logic ports 1:1 to node functions; orchestration changes only
- `MemorySaver` for dev; Postgres for prod (SEAM: checkpointer interface)

## Alternatives

### Alternative 1: Custom direct-async (JARVIS style)

- Pros: Simpler for small flows; zero dependencies; full control
- Cons: No checkpointing, no interrupts, no OTel, no parallel execution, manual state management

### Alternative 2: Microsoft Agent Framework

- Pros: Graph workflows, OTel, .NET + Python, Azure integration
- Cons: New (GA Oct 2025); less mature ecosystem; Microsoft ecosystem lock-in

### Alternative 3: Custom raw loop with manual checkpointing

- Pros: Zero dependencies; full control
- Cons: Reinventing checkpointing/interrupts/OTel; high maintenance burden

## Related

- ADR-001: Successor decision
- ADR-002: Pattern inheritance
- ADR-004: LearningHubSTEM consumer adapter contract (planned)
- ADR-005: Safety gate protocol (planned)
- `ARCHITECTURE.md` §2 (System Topology with LangGraph)
- `ARCHITECTURE-ESSENTIALS.md` §2 (System Topology at a Glance)
- `IMPLEMENTATION-PLAN.md` Phase 3 (Cognitive Engine with LangGraph)
