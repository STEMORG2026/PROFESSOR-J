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
- **Credentials and origins are server-owned.** A caller may not nominate the upstream origin for a
  credential the server holds; the allow-list lives in `app/adapters/auth.py`. A provider must have
  its settings declared in `app/config/settings.py` before it can be selected — the Bluesmind
  provider was selectable while `bluesmind_api_key` / `bluesmind_base_url` were undeclared, so
  choosing it raised `AttributeError` at runtime (S2-17). Declaration is part of adding a provider.
- **OpenTelemetry packages move in lockstep.** `opentelemetry-api`, `opentelemetry-sdk` and the
  OTLP exporters constrain each other (the exporter requires `opentelemetry-sdk~=<its own
  version>`), so they must be pinned to the *same* release. They were pinned to 1.29.0 / 1.29.0 /
  1.44.0, which is unsatisfiable: `pip install -r requirements.txt` failed with
  `ResolutionImpossible`, every CI job died in "Set up env" before running a single test, and a
  fresh clone could not be installed at all. Treat these three as one unit when upgrading.
- **Startup is logged.** `app/main.py` calls `setup_logging()` before serving, so startup is
  recorded structurally rather than inferred from stdout.

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
