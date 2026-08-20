# Constraints & Assumptions

> Companion: `constraints` v0.1.0 from ProjectTemplates 0.1.0
> Answers here are this project's source of truth.
> Re-generate or adopt a newer template only as a deliberate decision (`tpl update`).

---

## Hard constraints

- **Workspace governance:** Level-1 invariants are non-overridable (independent peers, no
  embedding, human review of AI output, derived-not-canonical, status honesty).
- **Naming:** PROFESSOR-J (renamed from JARVIS for copyright reasons).
- **Language/runtime:** Python 3.11+ backend; TypeScript/Next.js 15 frontend.
- **Boundaries:** `app/domain/` is pure; `app/brain/` never imports web frameworks;
  code execution only in the sandbox; no package-level coupling to other repos.
- **Single-tenant** personal platform first.

## Assumptions (that, if false, would change the design)

- LearningHubSTEM continues to publish a stable `exports/knowledge.json` with the expected
  schema (verified in Phase 1; schema drift is guarded by tests).
- The multi-provider LLM landscape remains accessible via the providers JARVIS already
  integrates (Ollama, llama.cpp, Google AI Studio, Groq, Cerebras, OpenAI, Anthropic,
  OpenRouter).
- ChromaDB and BM25 continue to meet retrieval needs at this scale.

## Boundaries (explicitly out of scope)

Multi-tenancy, payments, mobile native, guaranteed accuracy for ungrounded topics,
replacing human teachers, shared platform infrastructure.

## Known risks

- LLM provider availability changes (mitigated by circuit breakers).
- LearningHubSTEM export schema drift (mitigated by zero-drift adapter tests).
- Voice latency targets (WebRTC) hard to meet on weak networks (mitigated by VAD and
  fallback to text/SSE).
- Sandbox escape risk (mitigated by subprocess isolation, resource caps, HITL).

## Dependencies on other projects/systems

- **LearningHubSTEM** — canonical knowledge (consumer adapter, contract).
- **JARVIS** — patterns/capabilities (pattern-level inheritance, no coupling).
- **ProjectTemplates** — this document set's generator.

## Ethical / safety / confidentiality requirements

- Safety tiers on all tools; HITL for destructive operations.
- No secrets in code/docs.
- Learner data stored locally first (SQLite), encrypted where sensitive; no PII leaks in
  telemetry.
