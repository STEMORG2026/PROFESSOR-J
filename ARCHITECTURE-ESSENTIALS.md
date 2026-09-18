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

Status: **✓ implemented** · **~ scaffold/foundation** · **◇ planned**.

| Layer | Directory | Role & Key Components | Status |
|-------|-----------|-----------------------|--------|
| **Presentation** | `frontend/` | Next.js 15 UI, KaTeX math canvas, Plotly/D3 graphs, WebRTC Voice HUD. | ◇ planned |
| **Adapters** | `app/adapters/` | FastAPI REST, SSE streaming, WebSocket & WebRTC signaling, Bearer Auth. | ◇ planned |
| **Composition Root** | `app/bootstrap.py` | `ApplicationContainer` DI wiring singletons. | ◇ planned |
| **Orchestration** | `app/brain/` (LangGraph) | `StateGraph`, `Pregel` runtime, checkpointing, interrupts, streaming. | ~ minimal intent→plan→synthesize pipeline ✓; checkpointing/streaming ◇ |
| **Cognitive Brain** | `app/brain/` | `CognitiveBrain` (Intent→Plan→Synthesize); Professor/Research/Evaluator/ToolExecutor agents. | ~ brain pipeline ✓; agents ◇ |
| **Guardrails** | `app/guardrails/` | `@safety_gate` (`SAFE`/`SENSITIVE`/`DESTRUCTIVE`), `PromptInjectionDetector`, `PIIRedactor`. | ✓ implemented |
| **Knowledge** | `app/knowledge/` | `LHSKnowledgeAdapter` (LHSTEM seam), `GeneralKnowledgeAdapter`. | ✓ implemented |
| **Memory** | `app/memory/` | `MemoryService` (ChromaDB+BM25). | ◇ planned |
| **Database** | `app/db/` | `DatabaseEngine` (SQLite/Postgres mastery store). | ◇ planned |
| **Platform Services** | `app/session/`, `app/workspace/`, `app/tools/` | `SessionManager`, `WorkspaceManager`, sandboxed `ToolExecutor`. | ◇ planned |
| **Models & Resources** | `app/models/`, `app/resources/` | `ModelRouter` (multi-provider), `CircuitBreaker` (3-state), `TokenBudget`, `ProviderCatalog`. | ~ foundation ✓ (17+ real providers & task-type routing ◇) |
| **Skills** | `app/skills/` | `SkillRegistry` + built-ins (filesystem, git, LHS knowledge, web_search, code_execution, memory). | ✓ implemented |
|| **Orchestration** | `app/orchestration/`, `app/acp/` | `SubagentManager`, `PluginRegistry`, `AgentRouter`, `HooksSystem`, `SessionManager`, `ToolSearch`, `SandboxedExecution`, `TaskTracker`, `Scheduler`, `ACPServer`. | ✓ implemented (Phase 9+10+11) |
|| **SOTA Tools** | `app/tools/web.py`, `app/tools/browser.py`, `app/tools/computer_use.py` | `WebSearch`, `BrowserControl`, `ComputerUse`. | ✓ implemented (Phase 11) |
| **Observability** | `app/telemetry/` | OTel SDK (OpenInference), `LangfuseExporter`, `Tracer`, `MetricsCollector`. | ✓ exporter implemented |
| **Domain Layer** | `app/domain/` | Pure Python 3.11+ dataclasses (`LearnerState`, `ExecutionPlan`, `ConceptEntity`). | ✓ implemented |
| **Passive Telemetry** | `app/events/` | `InMemoryAsyncBus`, `EventLogger`, `MetricsCollector`. | ◇ planned |

---

## 3. Inviolable Dependency Rules

```
frontend/ ──► app/adapters/ ──► app/bootstrap.py ──► app/brain/ ──► app/domain/
                                                         │
                                                         ├──► app/guardrails/
                                                         ├──► app/knowledge/ & app/memory/
                                                         ├──► app/session/ & app/workspace/
                                                         ├──► app/models/ & app/resources/
                                                         ├──► app/mcp/
                                                         └──► app/telemetry/
```

- ❌ `app/domain/` MUST NOT import from any other layer (zero dependencies).
- ❌ `app/brain/` MUST NOT import directly from `app/adapters/` or web frameworks.
- ❌ Code execution MUST NOT run in the main server process; always via
  `app/tools/sandbox.py`.
- ❌ No package-level coupling to JARVIS or LearningHubSTEM (contracts/adapters only).
- ✅ All cross-layer communications go through DI in `app/bootstrap.py`.
- ❌ `app/mcp/` MUST NOT import from `app/brain/` (MCP is a tool provider, not a brain component).

---

## 4. Safety Gate Protocol

> **Implemented** in `app/guardrails/policy.py` (`SafetyPolicy` + `safety_gate`) with
> `PromptInjectionDetector` and `PIIRedactor`. DESTRUCTIVE tier raises
> `HITLRequiredError` unless an approval callback grants approval (fails closed).

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

## 7. MCP Client Quick Reference

```python
# app/mcp/client.py
class MCPServerManager:
    def __init__(self, config: MCPConfig):
        self.servers: dict[str, MCPServer] = {}

    async def connect_stdio(self, name: str, command: str, args: list[str]) -> None:
        """Connect to local MCP server via stdio."""
        ...

    async def connect_http(self, name: str, url: str, headers: dict = None) -> None:
        """Connect to remote MCP server via Streamable HTTP."""
        ...

    async def list_tools(self, server: str, cache: bool = True) -> list[Tool]:
        """List tools with optional caching (98% token reduction)."""
        ...

# app/mcp/tools.py
class CodeExecutionTools:
    """Present MCP tools as filesystem code APIs (Anthropic pattern)."""
    def write_tool_code(self, tool: Tool, path: Path) -> None:
        """Write Python wrapper for tool to ./servers/{name}/{tool}.py"""
        ...
```

**Transports:** stdio (local) + Streamable HTTP (remote). SSE is legacy.
**Tool Search:** On-demand loading — agent reads only needed tool definitions.
**Code-as-Tools:** Agent writes Python to call tools; PII stays in execution env.

---

## 8. Observability Quick Reference (Langfuse + OTel)

```python
# app/telemetry/exporter.py
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor

exporter = OTLPSpanExporter(endpoint="http://langfuse:4318/v1/traces")
processor = BatchSpanProcessor(exporter)
provider.add_span_processor(processor)

# Semantic conventions (OpenInference):
# span.kind = "agent" | "tool" | "retrieval" | "guardrail" | "evaluator" | "embedding" | "prompt"
# attributes: gen_ai.operation.name, gen_ai.model, gen_ai.usage.prompt_tokens, etc.
```

**Langfuse Self-Host:** `docker-compose -f docker/observability.yml up -d`
- Postgres (metadata) + ClickHouse (traces) + Langfuse UI
- Prompt Hub: versioned prompts, A/B testing
- Datasets: curated eval sets from production traces
- Evals: LLM-as-judge + code evaluators + CI gating

**Spans to Emit:** `agent` (cognitive steps), `tool` (sandbox/MCP), `retrieval` (vector/BM25),
`guardrail` (safety gate), `evaluator` (step verification), `embedding` (indexing).

---

## 9. Quick Verification Commands

```bash
# Backend
make test              # pytest (unit + integration + contract)
make typecheck         # mypy --strict app/
make lint              # pre-commit (ruff, trailing-whitespace, etc.)

# Observability
make langfuse-up       # docker-compose -f docker/observability.yml up -d
make langfuse-down     # docker-compose -f docker/observability.yml down

# Frontend (Phase 7+)
cd frontend && pnpm typecheck && pnpm lint
```
