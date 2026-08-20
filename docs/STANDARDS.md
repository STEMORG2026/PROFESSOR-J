# STANDARDS — PROFESSOR-J

**Status:** Coding, documentation, and working standards.
**Related:** `docs/RULES.md` (enforcement), `docs/CONSTITUTION.md` (constitution),
`AGENTS.md` (routing).

---

## 1. Coding standards

### 1.1 Python (backend, `app/`)

| Concern | Standard |
|---------|----------|
| Language | Python 3.11+ |
| Style | PEP 8; line limit 100 chars |
| Typing | `strict: true` in mypy; no untyped public functions |
| Docstrings | Google-style docstrings on all public modules/classes/functions |
| Domain purity | `app/domain/` = pure dataclasses; zero framework imports |
| Async | async/await throughout `app/brain/`; no blocking calls on the event loop |
| Naming | `snake_case` functions/vars, `CamelCase` classes, `_private` for internals |

### 1.2 TypeScript (frontend, `frontend/`)

| Concern | Standard |
|---------|----------|
| Framework | Next.js 15 App Router, React 19 |
| Type safety | strict mode; zero `any` |
| Styling | Tailwind CSS; existing theme tokens |
| State | Server-Sent Events (SSE) for streaming; WebSocket/WebRTC for voice |
| Naming | `camelCase` vars, `PascalCase` components |

### 1.3 Commits

- Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
- Branch names: `feature/xxx`, `fix/xxx`, `docs/xxx`.

---

## 2. Documentation standards

| Document | Where | Purpose |
|----------|-------|---------|
| README.md | root | What the project is, quickstart, doc map |
| AGENTS.md | root | Operating rules for humans and agents |
| PRD.md | root | Product requirements, vision, personas |
| ARCHITECTURE.md | root | Living system architecture |
| ARCHITECTURE-ESSENTIALS.md | root | Quick-reference cheat sheet |
| IMPLEMENTATION-PLAN.md | root | Phased roadmap and execution milestones |
| GOVERNANCE.md | `docs/` | Level-2 governance |
| CONSTITUTION.md | `docs/` | Development constitution |
| RULES.md | `docs/` | Enforceable rules |
| STANDARDS.md | `docs/` | This file |
| PRINCIPLES.md | `docs/` | Project values |
| WORKING-PROCEDURE.md | `docs/` | How work gets done |
| 100–601 modules | `docs/` | Project Operating System foundation answers |
| ADRs | `docs/adr/` | Decision records (MADR) |
| CHANGELOG | `docs/600-changelog.md` | Version history |

**Rules:**
- Every module (`app/`, `frontend/`) has a README describing purpose, usage, dependencies.
- Public APIs have docstrings/type signatures.
- Docs are updated in the same PR that changes the behavior they describe.
- AI-generated docs are drafts until human-reviewed.

---

## 3. Working standards

- **Verification before done:** run the repository verification commands (see
  `AGENTS.md` §5) before ending any work session.
- **TDD encouraged:** write tests alongside implementation.
- **Small increments:** small verified increments with clean boundaries beat speculative
  architecture.
- **Trail:** decisions → ADR; changes → changelog; commits reference both where relevant.
- **No silent scope expansion:** classify work and ask the human when in doubt.
