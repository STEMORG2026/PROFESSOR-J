# PROFESSOR-J Skill/Tool/MCP Audit — 2026-09-03

**Purpose:** Identify what PROFESSOR-J is missing from the workspace's available capabilities, given its role as the **ecosystem development agent** (knows all workspace skills/MCPs/tools/governance to develop the ecosystem).

---

## 1. Current PROFESSOR-J Capabilities (from `app/skills/builtin.py`)

| Skill | Status | Notes |
|-------|--------|-------|
| `filesystem` | ✅ Implemented | Read/write/list/exists/delete/mkdir |
| `git` | ✅ Implemented | status, diff, log, commit, branch, push, pull, add |
| `web_search` | ⚠️ **STUB** | Requires MCP brave-search server (not wired) |
| `code_execution` | ⚠️ **STUB** | Requires sandbox (Phase 5, not built) |
| `lhstem_knowledge` | ✅ Implemented | STEMMA canonical concepts, prerequisites, search |
| `memory` | ⚠️ **STUB** | Requires MemoryService (ChromaDB + BM25, not built) |
| `project_build` | ✅ Implemented | Build/test/lint/typecheck for Python, Node, Rust, Go |
| `git_extended` | ✅ Implemented | Extended git ops (branch, checkout, merge, rebase, stash, remote, tag, reset) |
| `file_template` | ✅ Implemented | Generate from templates (python_cli, react_component, python_fastapi) |
| `mcp` | ✅ Implemented | MCP server connect, list tools, call tools, list/read resources |

**ToolExecutor Registered Tools:**
- `run_code` (DESTRUCTIVE) - sandbox Python
- `solve_math` (SAFE) - SymPy
- `math_calculus` (SAFE) - differentiate/integrate
- `make_chart` (SAFE) - Plotly specs
- `gamedev_plan/scaffold/validate/verify` (SAFE/DESTRUCTIVE) - game dev tools

**MCP Layers (two coexisting):**
1. `app.mcp.client` - protocol/client layer (StdioMCPClient, SSEClient, MCPClientManager)
2. `app.mcp.manager` - management/config layer (MCPServerManager, safety-gated)

---

## 2. Workspace-Available Skills (in `~/.hermes/skills/`) — MISSING FROM PROFESSOR-J

### Critical for Ecosystem Development Agent

| Category | Skill | Why PROFESSOR-J Needs It |
|----------|-------|--------------------------|
| **GitHub** | `github-auth` | Auth setup for all GitHub operations |
| | `github-code-review` | Review PRs before merge — essential for development workflow |
| | `github-pr-workflow` | Branch → commit → PR → CI → merge lifecycle |
| | `github-issues` | Create/triage/label/assign issues |
| | `github-issue-to-pr` | Carry issue to verified PR with honest CI state |
| | `github-repo-management` | Clone/create/fork repos; manage remotes, releases |
| **Research** | `grounded-citations` | Every claim from external source gets verifiable citation |
| | `arxiv` | Search/retrieve academic papers (STEM knowledge expansion) |
| | `blocked-page-recovery` | Recover paywalled/WAF'd pages |
| | `llm-wiki` | Build interlinked markdown knowledge base |
| **Workspace Ops** | `workspace-synthesis` | Summarize multi-repo workspaces, read governance, check git |
| | `stem-workspace-agent-ops` | Phase-engineer repos to land PRs via auto-merge |
| | `safe-git-repo-delivery` | Safe git PR/merge across multi-repo projects |
| **Productivity** | `document-to-action-items` | Extract obligations, deadlines, tasks from documents |
| | `meeting-action-items` | Turn meeting notes into cited decisions, owners, tickets |
| | `weekly-review-planning` | Weekly reset: commitments, stalled work, next-week plan |
| **Email** | `himalaya` | IMAP/SMTP email from terminal |
| | `email-inbox-triage` | Prioritize threads, draft replies safely |
| **Agent Orchestration** | `autonomous-ai-agents/claude-code` | Delegate coding to Claude Code CLI |
| | `autonomous-ai-agents/codex` | Delegate coding to OpenAI Codex CLI |
| | `autonomous-ai-agents/opencode` | Delegate coding to OpenCode CLI |
| | `autonomous-ai-agents/computer-use` | Drive desktop background-first |
| | `professor-j-multi-agent-dev` | Build multi-agent dev systems for PROFESSOR-J using ECC |

---

## 3. Missing MCP Server Configurations

| MCP Server | Purpose | PROFESSOR-J Needs It? |
|------------|---------|----------------------|
| `github` | GitHub API via MCP (issues, PRs, repos) | **YES** — critical for development workflow |
| `brave-search` | Web search | **YES** — web_search skill stub depends on it |
| `filesystem` | File operations via MCP | Optional (has native skill) |
| `python` | Code execution via MCP | Optional (has native stub, needs sandbox) |
| `arxiv` | Paper search via MCP | **YES** — research capability |
| `semantic-scholar` | Citations, related papers | **YES** — research capability |

---

## 4. What Must Be Added to PROFESSOR-J (Priority Order)

### Tier 1: Critical — Ecosystem Development Agent Cannot Function Without

1. **GitHub Skills** (4 skills) — PR workflow, code review, issues, repo management
2. **Grounded Citations** — Verifiable sources for all external claims
3. **arXiv Research** — Academic paper search for STEM knowledge
4. **Workspace Synthesis** — Multi-repo awareness, governance reading, git status
5. **GitHub MCP Server Config** — Native GitHub API via MCP
6. **Brave Search MCP Server Config** — Unblocks `web_search` skill

### Tier 2: Important — Enables Full Development Autonomy

7. **Safe Git Repo Delivery** — Multi-repo PR/merge safety
8. **Stem Workspace Agent Ops** — Phase-engineer repos to land PRs
9. **Autonomous Agent Delegation** — Claude Code / Codex / OpenCode for parallel work
10. **Semantic Scholar MCP** — Citations, recommendations, author profiles
11. **Blocked Page Recovery** — Access paywalled content

### Tier 3: Useful — Enhances Productivity

12. **Document/Meeting Action Items** — Extract tasks from docs/meetings
13. **Weekly Review Planning** — Structured weekly reset
14. **Email Skills** — Communication workflows
15. **LLM Wiki** — Build interlinked knowledge base

---

## 5. Implementation Plan

### Immediate (This Session)
- Add Tier 1 skills as PROFESSOR-J native skills in `app/skills/builtin.py`
- Add MCP server configs for GitHub + Brave Search
- Wire `web_search` skill to Brave Search MCP
- Add `grounded_citations` skill (stdlib-only, no deps)
- Add `arxiv` skill (stdlib-only, no deps)
- Add `workspace_synthesis` skill (uses existing workspace scripts)

### Near-term
- Add Tier 2 skills
- Implement sandbox for `code_execution` skill
- Implement MemoryService for `memory` skill

### Configuration
- Add `mcp_servers.json` with GitHub + Brave Search configs
- Update `ToolExecutor` to register MCP tools from these servers

---

## 6. ADR Requirements

Each major skill addition should have an ADR in `docs/adr/` recording:
- Why this capability is needed for ecosystem development
- Pattern-level inheritance from Hermes skills (not package coupling)
- Verification approach

---

## 7. Status Honesty

| Capability | Current State | Target State |
|------------|---------------|--------------|
| GitHub operations | Missing | Full PR lifecycle via skills + MCP |
| Web search | Stub (requires MCP) | Working via Brave Search MCP |
| Code execution | Stub (requires sandbox) | Working via Phase 5 sandbox |
| Memory | Stub (requires MemoryService) | Working via Phase 5 MemoryService |
| Research (arXiv, citations) | Missing | Full grounded research pipeline |
| Workspace synthesis | Missing | Can summarize any repo |
| Multi-agent delegation | Missing | Can spawn Claude/Codex/OpenCode |
| Auto-merge delivery | Missing | Safe multi-repo PR/merge |

**Bottom line:** PROFESSOR-J currently has **internal** skills (filesystem, git, templates, build, STEMMA knowledge) but **lacks the external-facing development workflow skills** that make it an effective ecosystem development agent. The GitHub, Research, and Workspace Ops skills are the critical gaps.