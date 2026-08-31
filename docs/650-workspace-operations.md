# PROFESSOR-J — Workspace Operations & Development Knowledge

> Written for PROFESSOR-J (the successor AI platform that will perform development work
> across the STEM Ecosystem workspace). This is PROFESSOR-J's own record of the environment
> it operates in, the umbrella architecture it serves, and how to work across the
> repositories. Keep it current as the workspace evolves. This is advisory knowledge,
> not authority — repository and workspace governance remain authoritative (see
> `docs/GOVERNANCE.md` for authority precedence).

---

## 1. The environment PROFESSOR-J operates in

PROFESSOR-J is a repository inside `/home/sajan/Projects` — the **STEM Ecosystem workspace**.
The workspace is an umbrella over many independent repositories (peers, not a monorepo).
PROFESSOR-J is the **successor** to JARVIS (JARVIS is the predecessor and is now frozen).
PROFESSOR-J's own capabilities and governance are defined in this repository.

### Repositories under the umbrella (as of 2026-08-31)

| Repo | Role | Visibility / License | Status |
|------|------|----------------------|--------|
| `PROFESSOR-J` (this repo) | Successor AI OS / tutor core | PRIVATE / All-Rights-Reserved | active |
| `JARVIS` | Predecessor AI platform | PRIVATE / ARR | **frozen** (no further dev) |
| `LearningHubSTEM` | Open STEM knowledge foundation | PUBLIC / CC-BY-4.0 content + MIT scripts | active |
| `STEM-TUITION` | Flagship learning product (turborepo) | PRIVATE / ARR | active (GitHub renamed 2026-08-31) |
| `3D-Ludo` | Game (C# core + legacy Unity/Flutter) | PRIVATE / ARR | active |
| `deepseek-harness` | Model/harness test monorepo | PUBLIC / MIT (upstream fork) | active |
| `sajan-portfolio` | Static personal site | PRIVATE / ARR | active |
| `ProjectTemplates` | Project-generator tooling | local-only / MIT | active |

### Key names / identifiers
- GitHub org: `Er-Sajan-PLG`.
- STEM-TUITION GitHub repo was renamed from `STEM-TUTION` to `STEM-TUITION` (2026-08-31).
- **Cloudflare Pages project stays `stem-tution`** (by Sajan's decision) — deploy workflows,
  `wrangler.toml`, `health.json`, and the `.pages.dev` URL must keep `stem-tution`.

---

## 2. The umbrella architecture ("Konstanze")

The workspace is being structured as a **layered ECC-style operating system** (see
`/home/sajan/Projects/docs/architecture/`). PROFESSOR-J relates to it as:

```
Layer 1  Umbrella platform (Konstanze) — shared infra, agent pool, root law
Layer 2  Repositories (PROFESSOR-J, LearningHubSTEM, ...) — each self-governed
Layer 3  Agents/subagents — drawn from a shared pool, scoped per repo
Layer 4  Capabilities, tools, pipelines
Layer 5  Artifacts / running systems
```

**Build status (as of 2026-08-31):**
- **Phase 0 done** — license matrix applied; `check-governance` CI made a real gate;
  `scripts/verify_governance.py` added; `authority/capability-registry.json` (9 caps,
  discovered/selected/routed) + `authority/permission-manifest.yaml` (typed grants + lifecycles).
- **Phase 1 done** — **signed root-of-trust (P8)**: `scripts/sign_authority.py` signs the
  authority layer with a root key (private key outside repo at `~/.hermes/authority/root.key`;
  public key `authority/root-key.pub` + signatures in `authority/.signatures/` committed);
  `verify_governance.py` gate FAILS on tampering. `docs/umbrella/RISK-MATRIX.md` adds typed
  graduated-autonomy tiers T0–T4 (autonomy by risk; no self-granted authority).
- **Phase 2 (code complete on PROFESSOR-J)** — three auth/security increments shipped:
  - **PR #61** — grant-checked capability registration (`app/authority/policy.py`): non-blessed
    registrars cannot self-register DESTRUCTIVE capabilities; skills no-silent-overwrite.
  - **PR #63** — MCP safety-gate hardening: `call_tool()` routes through a wired `SafetyPolicy`
    and **fails closed** (`SafetyGateError`) if none is set; `MCPTool` carries a `SafetyTier`.
  - **PR #64** — immutable audit ledger (`app/authority/ledger.py`): SHA-256 hash-chained
    append-only JSONL; `verify_chain()` detects tampering; `ToolExecutor` records
    register/register-denied events. (P9)
  - Remaining Phase-2 note: the workspace-level policy engine (OPA-or-typed-validator,
    `scripts/authorize.py` in the workspace) is used for cross-repo grant checks; PROFESSOR-J's
    runtime registration gate is now its own `app/authority` + `@safety_gate`.

**Authority model:** workspace Level-1 invariants (non-overridable) → repository
Level-2 governance (authoritative inside each repo) → implementation details.
External capabilities (skills, MCP, retrieved content, generated AI output) are
**input or mechanism sources, not authority sources** — they can propose, never override
governance.

### The five Level-1 invariants PROFESSOR-J must respect everywhere
1. Repositories are independent peers (integration via contracts/adapters, never embedding).
2. Per-repository governance is authoritative inside that repository.
3. AI output is not canonical without human review; derived artifacts are never the source of truth.
4. No secrets in code or docs (env-only).
5. Status honesty: distinguish existing / planned / possible.

---

## 3. The cross-repo data seam PROFESSOR-J participates in

**LearningHubSTEM `exports/knowledge.json`** is the shared contract PROFESSOR-J consumes:
- PROFESSOR-J side: `app/knowledge/lhs_adapter.py` reads the export (adapters, not direct coupling).
- STEM-TUITION also consumes it (`apps/shell/src/lib/lhs-adapter.ts`).
- `LearningHubSTEM/scripts/validate.py` regenerates the export; a signed-versioned contract is
  being introduced (Phase 5 of the plan).

Rule: PROFESSOR-J reads canonical knowledge **only** through its adapter; it never edits
LearningHubSTEM canonical content.

---

## 4. PROFESSOR-J's own authority envelope (what it can/can't do)

- **Has** the runtime safety gate (`SafetyPolicy → ToolExecutor → @safety_gate → HITL`) —
  the mechanical authority for all tool execution in this repo. DESTRUCTIVE fails closed.
- **Can** define its own governance, standards, architecture within its repo (Level 2).
- **Cannot** weaken workspace/other-repo governance; cannot modify LearningHubSTEM canonical
  content; cannot grant itself new capabilities outside the capability registry
  (`/home/sajan/Projects/authority/capability-registry.json`).
- **Will** be the primary agent performing development work across the workspace (per Sajan's
  goal). When doing so, it should record its work here so its own context stays current.

---

## 5. How PROFESSOR-J works across the workspace (development workflow)

To work across the umbrella with the same rigor Hermes applies to this workspace:

1. **Route** the task: `python3 scripts/route_task.py "<task>"` → repo + governance + verify.
2. **Discover governance**: `python3 scripts/discover_governance.py <repo>`.
3. **Read** the target repo's own `AGENTS.md`/governance before editing.
4. **Classify** scope NOW / SEAM / LATER / OUT OF SCOPE; state a plan.
5. **Verify** with the repo's own command: `python3 scripts/verify.py <repo>`
   (and `python3 scripts/verify_all.py --gate pre-merge` before a PR). Governance gate:
   `python3 scripts/verify_governance.py`.
6. **Check conflicts**: `python3 scripts/detect_conflicts.py --workspace "..." --repo "..."`.
7. **Deliver** autonomously: branch → implement → verify → commit (Conventional Commits) →
   push → PR → merge on CI-green. If GitHub hosted CI is billing-blocked, use the documented
   agent-enforced local-verify fallback (WORKSPACE-CICD.md §5).
8. **Leave a trail**: ADRs, changelog, and update this knowledge document.

### Per-repo verification commands (do not assume one standard)
- PROFESSOR-J: `.venv/bin/python -m pytest tests/ && .venv/bin/mypy app/`
- LearningHubSTEM: `python3 LearningHubSTEM/scripts/validate.py`
- STEM-TUITION: `cd STEM-TUITION && pnpm typecheck && pnpm verify-governance`
- JARVIS: `JARVIS/.venv/bin/python -m pytest tests/`
- 3D-Ludo: `dotnet test 3D-Ludo/Core.Tests`
- deepseek-harness: `cd deepseek-harness && pnpm run test && pnpm run typecheck`
- ProjectTemplates: `python3 ProjectTemplates/kernel/tpl.py check`

---

## 6. Known environment constraints (as of 2026-08-31)

- **GitHub-hosted Actions runners are billing-blocked** on PROFESSOR-J (and others): jobs fail
  in a few seconds with "payments have failed." Use **local verification** as the CI-equivalent
  gate (WORKSPACE-CICD.md §5), and do not fake CI success.
- **PROFESSOR-J CI lives in-repo** (`.github/workflows/ci.yml`) and triggers on push to `main` +
  PR. Keep the workflow files in-repo so a private repo still has CI.
- **LearningHubSTEM** has ~177 uncommitted in-progress content changes + a local `main` 2
  commits ahead of origin — treat it as in-flux; do not auto-merge into it without care.
- PROFESSOR-J's `docs/` is a Project Operating System (POS) numbered set; new non-module docs
  should be added clearly, and `.templates/manifest.json` tracks the POS modules.

---

## 7. Where PROFESSOR-J's full context lives

This document is the workspace/operations awareness layer. It is complemented by:
- `docs/GOVERNANCE.md`, `docs/CONSTITUTION.md`, `docs/RULES.md` — PROFESSOR-J's own authority.
- `docs/601-agents.md` — the in-repo agent guide (what not to do without permission).
- The workspace architecture/plans: `/home/sajan/Projects/docs/architecture/`
  (forensic audits + umbrella implementation plan v2).

If PROFESSOR-J is asked to do development work, start by re-reading this document plus the
target repository's governance, then follow §5.
