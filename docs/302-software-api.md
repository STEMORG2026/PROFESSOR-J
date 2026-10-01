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
| Auth | Bearer token (`PROFESSOR_API_KEY`), enforced per router | header | all clients |
| LHS knowledge | file contract: `exports/knowledge.json` schema | `export_version` / `schema_version` (currently `0.1`) | `app/knowledge/` |
| Provider pool | provider API contracts (per provider) | pinned catalogs | `app/models/` |

## Authentication & egress allow-listing (enforced)

Both controls live in `app/adapters/auth.py` and both **fail closed**. They exist because an audit
established that all 34 routes were reachable without credentials (S0-1) and that a caller-supplied
`base_url` was paired with the server's own provider credential (S0-2).

**Ingress.** Routers are mounted with `dependencies=[Depends(require_api_key)]`. A request must carry
the configured bearer token. If that token is absent **or is a known placeholder**, *every* request
is rejected and the reason is logged — a placeholder token is not a weaker password but a publicly
known one, so honouring it would be worse than no check at all, because it would appear in the route
table as an enforced dependency while enforcing nothing.

**Egress.** `resolve_base_url(candidate, default)` decides which upstream origins the server may be
pointed at, and whether a credential the *server* owns may be sent there. A server-side provider
credential may travel only to an allow-listed origin; a caller that nominates its own origin must
supply its own credential. Precedence:

1. Origins named in `PROFESSOR_ALLOWED_BASE_URLS` (comma-separated).
2. Provider endpoints the server itself owns (`singularity_base_url`, `bluesmind_base_url`).
3. Loopback origins on any port — the local-inference path (Ollama, llama.cpp), which cannot
   exfiltrate a credential off the machine.

**Removed, not deprecated:** the caller-supplied `base_url` field on provider-select routes. Pairing
a caller's URL with the server's own `DEFAULT_API_KEY` handed the workspace credential to an
arbitrary host.

## Contract format & versioning discipline

- REST/SSE/WS paths are versioned (`/api/v1/...`); breaking changes = new major segment.
- LHS export schema is validated at import; drift fails loudly (zero-drift tests).
- Provider catalogs are live/derived, never hardcoded fallbacks.
- **Prerequisite mapping (SEAM):** The export has no literal `prerequisite` edge type.
  Prerequisite traversal derives from `mathematically_requires` and `logically_requires`
  relationship types. This mapping is a Phase 1 adapter decision and will be recorded in
  an ADR.

## Failure modes & caller handling

- Provider 429/503 → circuit breaker failover (sub-200ms), caller transparent.
- LHS schema drift → adapter throws typed error; system routes to general (ungrounded)
  path rather than crashing.
- Sandbox timeout/OOM → typed `SandboxError` with reason; UI shows it.
- SSE disconnect → client auto-reconnect with session token.

## Evolution & deprecation

- New endpoints ship under `/api/v2/` before deprecating `/v1`.
- Contracts require an ADR to change (see `docs/301-decisions.md`).
