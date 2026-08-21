# PROFESSOR-J — Implementation Plan & Roadmap

> **Master Engineering Roadmap**
> **Status:** Active Execution Plan
> **Phases:** 0 through 9
> **Related:** `PRD.md` (what), `ARCHITECTURE.md` (how), `docs/GOVERNANCE.md` (rules)

---

## 1. Roadmap Overview

```
PHASE 0 ░░░░░░░░░░  Governance, Workspace Setup & Bootstrap Foundation
PHASE 1 ░░░░░░░░░░  Core Domain Models & LearningHubSTEM Consumer Seam
PHASE 2 ░░░░░░░░░░  Multi-Provider Model Pool & Circuit Breakers
PHASE 3 ░░░░░░░░░░  Cognitive Engine (JARVIS-class) + Socratic Agents
PHASE 4 ░░░░░░░░░░  Platform Parity: Session, Workspace, Memory, Tools
PHASE 5 ░░░░░░░░░░  Code & Math Sandbox Execution Engine
PHASE 6 ░░░░░░░░░░  Knowledge, Research & PDF Ingestion Pipeline
PHASE 7 ░░░░░░░░░░  Next.js 15 Interactive Canvas UI
PHASE 8 ░░░░░░░░░░  WebRTC Real-Time Voice Classroom
PHASE 9 ░░░░░░░░░░  Mastery Tracking, Production & CI/CD Pipeline
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

### Phase 1: Core Domain Models & LearningHubSTEM Consumer Seam
- [ ] Author pure Python dataclasses in `app/domain/` (`LearnerState`,
      `PedagogicalTurn`, `MisconceptionState`, `ConceptEntity`, `ExecutionPlan`,
      `ToolCallRequest`).
- [ ] Implement `app/knowledge/lhs_adapter.py` reading
      `LearningHubSTEM/exports/knowledge.json`.
- [ ] Implement `GeneralKnowledgeAdapter` fallback (labeled ungrounded).
- [ ] Write unit tests verifying zero schema drift and prerequisite-graph traversal.
- **Acceptance Criteria:** 100% test coverage for domain models and LHS adapter.

### Phase 2: Multi-Provider Model Pool & Circuit Breakers
- [ ] Port and harden JARVIS's multi-provider model router into `app/models/` and
      `app/resources/` (ADR-documented port).
- [ ] Implement live dynamic catalogs in `app/utils/catalogs/` without hardcoded fallbacks.
- [ ] Implement 3-state circuit breakers (`CLOSED`, `OPEN`, `HALF_OPEN`) with automated
      429/503 failover.
- **Acceptance Criteria:** Router switches to fallback provider on simulated rate limits.

### Phase 3: Cognitive Engine (JARVIS-class) + Socratic Agents
- [ ] Implement `CognitiveBrain` (IntentAnalyzer → TaskPlanner → ExecutionRunner →
      ResponseSynthesizer), ported from JARVIS and upgraded.
- [ ] Implement `ProfessorAgent` (dialogue state machine, pedagogical scaffolding).
- [ ] Implement `EvaluatorAgent` (step-by-step math proof checking, logic validation).
- [ ] Implement `ToolExecutorAgent` (tool dispatching and result synthesis).
- [ ] Wire direct async cognitive loop in `app/brain/`.
- **Acceptance Criteria:** Agent guides a simulated student through Newton's 2nd Law
      without revealing the final answer directly.

### Phase 4: Platform Parity — Session, Workspace, Memory, Tools
- [ ] Port `SessionManager` and `WorkspaceManager` from JARVIS patterns.
- [ ] Port hybrid memory (`MemoryService`: ChromaDB dense + BM25 sparse).
- [ ] Port `ToolExecutor` and tool registry behind `@safety_gate`.
- [ ] Enable general-purpose chat/file/workspace assistance (non-education paths).
- **Acceptance Criteria:** ≥ 90% of JARVIS capabilities operational (platform parity).

### Phase 5: Code & Math Sandbox Execution Engine
- [ ] Implement `app/tools/sandbox.py` (isolated subprocess, CPU/memory limits, timeout
      watchdog).
- [ ] Implement SymPy solver tool (algebra, calculus, unit conversions).
- [ ] Implement Plotly/Matplotlib chart generator tool.
- [ ] Enforce `@safety_gate` tiers with HITL.
- **Acceptance Criteria:** Sandbox prevents harmful filesystem calls and terminates
      infinite loops cleanly.

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
- [ ] Implement `DatabaseEngine` with SQLite (local) and PostgreSQL support.
- [ ] Implement mastery calculation (Bayesian Knowledge Tracing / IRT).
- [ ] Persist transcripts, diagnostic histories, mastery trees.
- [ ] Create GitHub Actions CI (lint, mypy, pytest, Next.js build, Playwright E2E).
- [ ] Configure Cloudflare Pages (frontend) and containerized FastAPI (backend).
- [ ] Load testing (100 concurrent streaming sessions).
- **Acceptance Criteria:** CI green and automated deploy succeeds.

---

## 3. Scope Discipline

| Class | Items |
|-------|-------|
| **NOW** | Phases 0–9 as prioritized by the roadmap |
| **SEAM** | `IAuthService`-style seams: LHS adapter, voice provider, DB engine (SQLite→Postgres), distributed event bus (Redis/NATS LATER) |
| **LATER** | Multi-node scale-out, mobile native, multi-tenancy, payments |
| **OUT OF SCOPE** | Becoming a backend for any other repo; package-level coupling to JARVIS/LearningHubSTEM; speculative shared infrastructure |

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
