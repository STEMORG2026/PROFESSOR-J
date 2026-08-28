# PROFESSOR-J Frontend (Phase 7)

Next.js 15 + React 19 + Tailwind 4 chat/tutoring canvas for the PROFESSOR-J AI OS.

## Run it (two terminals)

**1. Start the backend (FastAPI).** From the repo root:

```bash
.venv/bin/python -m uvicorn app.adapters.api:app --host 127.0.0.1 --port 8000
```

Runs with the deterministic MockProvider — **no API keys needed**. Responses are
canned, but the full request/response path (Next → FastAPI → brain → UI) is real
so you can test the UI wiring.

**2. Start the frontend:**

```bash
cd frontend && pnpm install && pnpm dev
```

Open http://localhost:3000. The Next dev server proxies `/api/*` to the backend
(see `next.config.ts`; override with `API_BASE_URL`).

## Scripts

| Command | What it does |
|---|---|
| `pnpm dev` | Next dev server (Turbopack) on :3000 |
| `pnpm build` | Production build |
| `pnpm start` | Serve the production build |
| `pnpm lint` | ESLint |

## Backend endpoints

- `GET  /api/health` — subsystem liveness.
- `POST /api/chat`  — `{ "prompt": "...", "session_id": "..." }` → brain response.

## Notes

- `pnpm-workspace.yaml` whitelists `sharp`/`unrs-resolver` postinstall builds
  (pnpm 11 blocks build scripts by default).
- Point `API_BASE_URL` at a real deployed backend in production; the LHS export
  path and model provider are injected by the backend, not the frontend.
