# PROFESSOR-J — Architecture Essentials

> **Quick-Reference Cheat Sheet for Developers & AI Agents**
> Read this file for rapid orientation before modifying code in `PROFESSOR-J`.

---

## 1. What PROFESSOR-J is

**A general-purpose autonomous AI platform (AI OS)** — inheriting JARVIS's cognitive brain,
tool sandbox, hybrid memory, multi-provider routing with circuit breakers,
session/workspace management — plus primary domains of tutoring, research, and pedagogy.
It **consumes LearningHubSTEM as one specialized knowledge source** via a consumer adapter
and falls back to general knowledge where no canonical entity exists. General by default,
specialized on demand.

---

## 2. System Topology at a Glance

| Layer | Directory | Role & Key Components |
|---|---|---|
| **Presentation** | `frontend/` | Next.js 15 UI, KaTeX math canvas, Plotly/D3 graphs, WebRTC Voice HUD. |
| **Adapters** | `app/adapters/` | FastAPI REST, SSE streaming, WebSocket & WebRTC signaling, Bearer Auth. |
| **Composition Root** | `app/bootstrap.py` | `ApplicationContainer` DI wiring singletons. |
| **Cognitive Brain** | `app/brain/` | `CognitiveBrain` (Intent→Plan→Execute→Synthesize), `ProfessorAgent`, `ResearchAgent`, `EvaluatorAgent`, `ToolExecutorAgent`. |
| **Guardrails** | `app/guardrails/` | `@safety_gate` (`SAFE`/`SENSITIVE`/`DESTRUCTIVE`), `PromptInjectionDetector`. |
| **Knowledge & Memory** | `app/knowledge/`, `app/memory/`, `app/db/` | `LHSKnowledgeAdapter` (LearningHubSTEM seam), `GeneralKnowledgeAdapter`, `MemoryService` (ChromaDB+BM25), `DatabaseEngine`. |
| **Platform Services** | `app/session/`, `app/workspace/`, `app/tools/` | `SessionManager`, `WorkspaceManager`, sandboxed `ToolExecutor`. |
| **Models & Resources** | `app/models/`, `app/resources/` | `ModelRouter` (multi-provider), `ResourceManager` (3-state circuit breakers). |
| **Domain Layer** | `app/domain/` | Pure Python 3.11+ dataclasses (`LearnerState`, `ExecutionPlan`, `ConceptEntity`). |
| **Passive Telemetry** | `app/events/`, `app/telemetry/` | `InMemoryAsyncBus`, `EventLogger`, `MetricsCollector`. |

---

## 3. Inviolable Dependency Rules

```
frontend/ ──► app/adapters/ ──► app/bootstrap.py ──► app/brain/ ──► app/domain/
                                                        │
                                                        ├──► app/guardrails/
                                                        ├──► app/knowledge/ & app/memory/
                                                        ├──► app/session/ & app/workspace/
                                                        └──► app/models/ & app/resources/
```

- ❌ `app/domain/` MUST NOT import from any other layer (zero dependencies).
- ❌ `app/brain/` MUST NOT import directly from `app/adapters/` or web frameworks.
- ❌ Code execution MUST NOT run in the main server process; always via
  `app/tools/sandbox.py`.
- ❌ No package-level coupling to JARVIS or LearningHubSTEM (contracts/adapters only).
- ✅ All cross-layer communications go through DI in `app/bootstrap.py`.

---

## 4. Safety Gate Protocol

Every tool executed by `ToolExecutorAgent` must be decorated with `@safety_gate`:

```python
from app.guardrails.policy import safety_gate, SafetyTier

@safety_gate(tier=SafetyTier.SAFE)
async def lookup_concept(concept_id: str) -> dict:
    """Read-only concept lookup: auto-approved."""
    ...

@safety_gate(tier=SafetyTier.DESTRUCTIVE)
async def execute_python_code(code: str) -> dict:
    """Runs code in sandbox: requires explicit Human-In-The-Loop approval."""
    ...
```

---

## 5. LearningHubSTEM Consumer Seam

PROFESSOR-J consumes canonical concepts without touching canonical source files:

```python
# app/knowledge/lhs_adapter.py
class LHSKnowledgeAdapter:
    def __init__(self, export_path: str = "LearningHubSTEM/exports/knowledge.json"):
        self.export_path = export_path
        self._cache = {}

    def get_concept(self, entity_id: str) -> Optional[ConceptEntity]:
        # Returns parsed ConceptEntity with prerequisites and equations
        ...

    def has_concept(self, entity_id: str) -> bool:
        # False → caller routes to GeneralKnowledgeAdapter (labeled ungrounded)
        ...
```

---

## 6. JARVIS Relationship Note

PROFESSOR-J inherits JARVIS's patterns and capabilities under a new name. JARVIS remains an
independent, maintained peer. Ports are adapted under this governance and recorded in
`docs/adr/` — never imported at the package level. PROFESSOR-J is **not a JARVIS fork**;
it is a general-purpose AI OS that reuses JARVIS's proven patterns.

---

## 7. Quick Verification Commands

```bash
.venv/bin/python -m pytest tests/   # Python backend tests
.venv/bin/mypy app/                 # strict typecheck
cd frontend && pnpm typecheck && pnpm lint
```
