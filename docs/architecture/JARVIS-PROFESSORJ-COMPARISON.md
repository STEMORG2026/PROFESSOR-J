# JARVIS vs PROFESSOR-J — Subsystem Comparison & SOTA Benchmark

**Status:** Trail record — 2026-09
**Scope:** Where PROFESSOR-J stands relative to JARVIS (its inherited pattern source) and
SOTA agent stacks, and what was added to close the gaps.

---

## 1. Where PROFESSOR-J exceeds JARVIS (genuine differentiators)

| Area | PROFESSOR-J | JARVIS | Notes |
|------|-------------|--------|-------|
| **Authority / Identity** | `app/authority/` — signed `AuthorityGateway`, Principals, allocation/capability registry, provenance enforcement | none | PROFESSOR-J's strongest original layer |
| **Canonical knowledge** | `app/knowledge/` LHS adapter (LearningHubSTEM seam) + general fallback | minimal | Consumer of the workspace knowledge foundation |
| **MCP client** | `app/mcp/` (stdio + Streamable HTTP, registry, tool-search) | none | External-tool integration |
| **Voice** | `app/voice/` (Piper TTS + faster-whisper STT) | none | - |
| **DB / mastery** | `app/db/` SQLite + mastery/transcript repos | less structured | - |

## 2. Gaps PROFESSOR-J had, now closed (benchmarked against SOTA)

| JARVIS capability | SOTA context | PROFESSOR-J before | Status |
|-------------------|--------------|--------------------|--------|
| `app/memory/` rich schema + behavior lifecycle | Mem0/CrewAI/LangMem decompose memory into extract→manage→store→rank | thin `MemoryBackend` seam + naive word overlap | **MERGED (PR #75)** |
| `app/memory/` hybrid retrieval (sparse+optional dense) + weighted ranker | CrewAI composite scoring; LangMem hybrid | naive overlap | **MERGED (PR #75)** |
| `app/memory/` fact extraction | Mem0 LLM-extraction (rule-based is a valid lighter path) | none | **MERGED (PR #75)** |
| `app/events/` InMemoryAsyncBus | event-driven observability (LangGraph checkpointer, OpenTelemetry) | only referenced in ARCHITECTURE diagram | **MERGED (PR #76)** |
| `app/context/` ContextWindowManager | context recomposition is core in CrewAI/Mem0 | no token trimming | **MERGED (PR #76)** |
| `app/prompt/` externalized prompt loader | Langfuse PromptHub pattern | none | **MERGED (PR #76)** |

## 3. Remaining gaps (not yet added — reasons)

| JARVIS capability | Why not added (SOTA check) |
|-------------------|----------------------------|
| `app/integrations/vector` (dense embeddings) | The dense vector leg is the documented Phase 4/6 pending item; requires an embedding model/service. Better done as its own effort alongside the memory dense retriever. |
| `app/integrations/ocr` | PaddleOCR for scanned PDFs is explicitly external-infra/deferred (Phase 6). |
| `app/utils/` provider catalogs (Groq/Cohere/Mistral/…) | PROFESSOR-J already has a provider `catalog.py` with its own curated defaults; the JARVIS catalogs are per-vendor config duplicates, not a capability gap. |
| `app/conversation/` manager | Covered by PROFESSOR-J `app/session/session_manager.py`. No gap. |
| `app/agents/`, `app/api/` | PROFESSOR-J routes agents/APIs through its authority/safety-gated architecture instead; different but not missing. |

## 4. Design decision honored

Both systems, and SOTA, favor **modular service objects over an event bus for stateful
memory**: the event bus (`InMemoryAsyncBus`) is reserved for *passive* telemetry/metrics,
never the data path. CONFirmed by JARVIS's own docstring ("core execution loops MUST use
direct async interface calls instead of the bus") and by the 2026 agent-memory survey
(modular four-stage decomposition: extract → manage → store → retrieve).

---

*Trail record for the JARVIS-parity work delivered in PRs #75 and #76.*