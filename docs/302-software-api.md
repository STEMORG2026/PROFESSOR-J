# Interfaces & Contracts

> Companion: `software-api` v0.1.0 from ProjectTemplates 0.1.0
> Answers here are this project's source of truth.
> Re-generate or adopt a newer template only as a deliberate decision (`tpl update`).

---

## External interfaces (must remain stable)

| Interface | Protocol | Versioning | Consumer |
|-----------|----------|------------|----------|
| Chat/stream | POST `/api/v1/chat/stream` → SSE | `/v1` in path | frontend |
| Voice signaling | WS `/api/v1/voice/signal` (WebRTC) | `/v1` in path | frontend |
| Auth | Bearer token (`PROFESSOR_API_KEY`) | header | all clients |
| LHS knowledge | file contract: `exports/knowledge.json` schema | schema `user_version` | `app/knowledge/` |
| Provider pool | provider API contracts (per provider) | pinned catalogs | `app/models/` |

## Contract format & versioning discipline

- REST/SSE/WS paths are versioned (`/api/v1/...`); breaking changes = new major segment.
- LHS export schema is validated at import; drift fails loudly (zero-drift tests).
- Provider catalogs are live/derived, never hardcoded fallbacks.

## Failure modes & caller handling

- Provider 429/503 → circuit breaker failover (sub-200ms), caller transparent.
- LHS schema drift → adapter throws typed error; system routes to general (ungrounded)
  path rather than crashing.
- Sandbox timeout/OOM → typed `SandboxError` with reason; UI shows it.
- SSE disconnect → client auto-reconnect with session token.

## Evolution & deprecation

- New endpoints ship under `/api/v2/` before deprecating `/v1`.
- Contracts require an ADR to change (see `docs/301-decisions.md`).