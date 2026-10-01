# PROFESSOR-J — Audit & Current State

> **Status:** Judgement-completed audit, folded into the USA deterministic report.
> **Commit audited:** `de7864f` (`main`, = `origin/main`, 0 ahead / 0 behind)
> **Date:** 2026-09-30
> **Tooling:** USA v2.26.0 (in-repo build), deep depth. Deterministic raw report: `/tmp/PJ-AUDIT-USA-v226.md`.
> **Maturity profile:** MVP / Early product (auto-detected; score 69.4/100 — within the 45–75 expected band).

This document is the **judgement layer** on top of the deterministic USA pass. Every
finding carries `file:line` evidence or command output. Nothing here is marked ✅ without
evidence, and the two USA findings I could disprove are recorded as false positives.

---

## 1. Verified state — what actually runs today

| Check | Command | Result |
|---|---|---|
| Unit/integration tests | `.venv/bin/python -m pytest tests/ -q` | **771 tests, 759 passed, 12 failed, 0 skipped** (69s) |
| Type checking | `.venv/bin/mypy app/` | ✅ **clean** — 137 source files, strict |
| Coverage | `pytest --cov=app` | 76% (domain layer carries its own ≥95% CI gate) |
| Lint | `.venv/bin/pre-commit run --all-files` | ❌ **ruff fails** — 79 errors + `E402` in an authority test |
| Repo verify entrypoint | `scripts/verify.py` | ❌ fails at step 1 (it runs pytest first, then mypy, then pre-commit) |
| CI on `main` | `gh run list --branch=main` | ❌ **red** on every run back to 2026-09-02 |
| Open PRs | `gh pr list` | 10 Dependabot PRs, all CI-red, auto-merge blocked |
| Worktree | `git status --porcelain` | clean (audit was read-only; pre-commit autofixes were reverted) |

**Runtime:** Python 3.14.7 in `.venv`. No PROFESSOR-J process is currently running.
Port `8000` is owned by **JARVIS** (`/home/sajan/Projects/JARVIS/.venv/bin/python -m app.main`,
up 41h) — see Finding C3.

---

## 2. What the repo claims vs. what is true

The repo's own status documents are internally consistent and honest about *unbuilt* work
(`IMPLEMENTATION-PLAN.md` §2b explicitly separates "implemented & tested" from "genuinely
external-infra / not implemented"). The drift is not in ambition — it is that **the claims
are stale relative to CI**, and one governance claim is documented but absent.

| Claim | Source | Reality |
|---|---|---|
| "CI green (from Phase 0.5)" | `IMPLEMENTATION-PLAN.md` Phase 9 acceptance criteria | CI has been red since 2026-09-02 |
| "The CI pipeline, branch protection, and Dependabot auto-merge are fully operational" | `IMPLEMENTATION-PLAN.md` §2b closing line | CI is red; the 10 open Dependabot PRs prove auto-merge is *not* operational |
| "`scripts/verify_governance.py` added" | `docs/650-workspace-operations.md:55` | **File absent** — `scripts/` contains only `verify.py`, `verify_export_contract.py`, `verify_git_safety.py`, `board/` |
| Repo table row `LearningHubSTEM` … active | `docs/650-workspace-operations.md:26` | No `LearningHubSTEM` directory in the workspace; the knowledge foundation is now `STEMMA` (also absent from the table) |
| "Suite green, mypy strict, board 8/8" | `IMPLEMENTATION-PLAN.md` §2b | mypy is green; the suite is not (12 failures) |

---

## 3. Findings

Priority order: **security > correctness > maintainability > style**.

### 🔴 Finding A1 — CRITICAL: `POST /api/skills/execute` violates three BLOCK-level rules of the repository's own constitution

**The single most serious finding. It is a genuine `⚠️ WRONG`, not a gap — and it is not
merely an architecture-doc mismatch. It breaches normative, BLOCK-severity rules.**

`docs/CONSTITUTION.md:58–61` — constitutional invariants 5 and 6:

> 5. **Sandboxed execution.** Code execution never runs in the host web-server process; it
>    runs in an isolated, resource-capped sandbox behind `@safety_gate`.
> 6. **Safety by default.** Every tool has an explicit safety tier; destructive operations
>    require human-in-the-loop approval.

`docs/RULES.md:17–19` marks each of these **BLOCK** — a rule that *stops the change at the
gate*:

| Rule | Severity | Enforcement declared |
|---|---|---|
| All tool execution passes through `@safety_gate` | **BLOCK** | Import check in review |
| Code execution runs only in the sandbox | **BLOCK** | Import check in review |
| `DESTRUCTIVE` operations require human-in-the-loop approval | **BLOCK** | HITL gate in execution runner |

`AGENTS.md` §3.4 restates the same constraint. **The route below breaks all three at once —
and the declared enforcement ("import check in review") is a manual review step, which is why
it was not caught.** That enforcement gap is itself recorded as Finding A8.

The sanctioned path does enforce this — `app/tools/executor.py:332` calls
`self.policy.check(...)` before dispatch, and the composition root is the only blessed
registrar (`app/bootstrap.py:135`).

The HTTP skill path does not. `app/adapters/api.py:878–902`:

```python
@app.post("/api/skills/execute", response_model=SkillExecuteResponse)
async def execute_skill(req: SkillExecuteRequest) -> SkillExecuteResponse:
    registry = SkillRegistry()            # fresh registry per request
    register_builtin_skills(registry)
    skill = registry.get(req.skill_name)
    result = await skill(**req.params)    # direct call — no policy, no gate, no HITL
```

Evidence that nothing protects this path:

- `grep -c 'safety_gate' app/skills/builtin.py` → **0**. No builtin skill is gated.
- The builtin skills include genuinely destructive and arbitrary-execution surfaces:
  - `shutil.rmtree(path)` — `app/skills/builtin.py:219` (filesystem `delete` operation)
  - `subprocess.run(cmd, ...)` — `app/skills/builtin.py:754`, `:853`, `:1659`, `:1833`, `:1941`, `:2062`
  - `urllib.request.urlopen(req, ...)` — `app/skills/builtin.py:1591`
- **No route in `app/adapters/api.py` has any authentication dependency.** All 28
  `@app.get/post/delete` decorators (lines 423–908) are bare — no `Depends`, no
  `HTTPBearer`, no API-key check. The `api_key` field in the request models
  (e.g. `app/adapters/api.py:68`) is an *upstream LLM provider key*, not caller auth.

**Reachability is currently latent, not live:** no PROFESSOR-J server is running, so this is
not an open door at this moment. It becomes an open door the first time
`app/main.py:121` is started as written — `uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)`
binds all interfaces with the reloader on.

**Compounding factor (CORS):** `app/adapters/api.py:413–418` sets
`allow_origins=["*"]`, `allow_methods=["*"]`, `allow_headers=["*"]`. Once the server runs,
**any website the browser visits can issue a cross-origin `POST /api/skills/execute` against
`localhost:8000`** and drive `shutil.rmtree` / `subprocess.run`. No preflight rejection
applies, because `*` is echoed back.

**Which file:line is authoritative:** `app/adapters/api.py:878` (the ungated route) is the
defect. `app/tools/executor.py:332` shows the correct pattern to route through.

### 🔴 Finding A2 — CORRECTNESS: `main` is red, and this blocks everything downstream

**12 failures / 771 tests**, in three independent root causes:

**(a) 8 failures — a governance surface is documented as existing but does not.**
`tests/unit/authority/test_phase6_security.py:18` and
`tests/unit/authority/test_build1_identity_gateway.py` both hardcode
`WORKSPACE_ROOT = Path("/home/sajan/Projects")` and then require
`/home/sajan/Projects/authority/allocation.yaml`. That path does not exist. The file exists
only *inside* the repo at `authority/allocation.yaml` (which does contain a `repo_allocation`
map covering PROFESSOR-J, STEMMA, and others).

This is a **Level-1 workspace question, not a repo bug**: either the umbrella `authority/`
tree is meant to exist at the workspace root and was never created, or the tests assert a
fabric that was never agreed. Notably, `/home/sajan/Projects/docs/WORKSPACE-GOVERNANCE.md`
does not mention `authority/` at all. **Do not "fix" this by editing the tests until the
umbrella decision is made.**

**(b) 3 failures — a genuine cross-repo contract break with STEMMA** (see Finding A3).

**(c) 1 failure — a broken test assertion.**
`tests/unit/voice/test_voice.py::test_piper_download_voice_downloads_both_files` asserts
`len(downloaded) == 2`, but the mock returns 4 entries — each URL appears to be accumulated
across iterations. Self-contained, mechanical fix.

### 🔴 Finding A3 — HIGH: the LearningHubSTEM/STEMMA consumer contract has silently drifted

This is the highest-value *engineering* finding, and it is a cross-repo contract violation
rather than a local bug.

`app/knowledge/lhs_adapter.py:43–44` pins the consumer contract:

```python
EXPECTED_EXPORT_VERSION = "0.1"
EXPECTED_SCHEMA_VERSION = "0.1"
```

and `app/knowledge/lhs_adapter.py:80–90` requires six top-level fields including
`generated_at`.

The real export at `/home/sajan/Projects/STEMMA/exports/knowledge.json` now carries:

| Field | PROFESSOR-J expects | STEMMA ships today |
|---|---|---|
| `export_version` | `0.1` | **`2.2.0`** |
| `schema_version` | `0.1` | **`1.3.0`** |
| `generated_at` | required | **absent** (replaced by `content_hash`) |

All three structural contract tests fail with
`LHSAdapterError: LHS export missing required fields: {'generated_at'}` —
`tests/unit/knowledge/test_lhs_adapter.py:162,170,177`.

**This is a documented, deliberate STEMMA decision that was never propagated into
PROFESSOR-J.** STEMMA's `archive/old-design/docs/decisions/0022-version-source-deterministic-exports.md`
records that wall-clock `generated_at` was deliberately replaced by a deterministic
`content_hash`, and explicitly states:

> `export_version` remains `"0.1"` — **the consumer contract does not change** (ADR-0019
> freeze; a contract bump is gate G-A with consumer co-release).

STEMMA has since moved `export_version` to `2.2.0` anyway
(`STEMMA/docs/CONSUMERS.md`: *"Consumer contract: `export_version: 2.2.0` (ADR-0050)… reader
support for 2.1.x still works"*) and its own consumer registry already lists **PROFESSOR-J as
a formal consumer** with an agreed contract. So STEMMA has a published contract and a
registered consumer; the consumer's adapter was never co-released. That is the definition of
the drift ADR-0019 existed to prevent.

**Mitigating context:** `app/bootstrap.py:126–131` catches adapter failure and degrades to
"no canonical knowledge". So this does not crash the platform — it silently removes the
pedagogical-provenance guarantee that `AGENTS.md` §3.2 promises. A silent correctness
downgrade is worse than a crash.

The adapter's *fixture* tests still pass, because `tests/fixtures/lhs_knowledge_fixture.json`
still contains the old `0.1` shape — the fixture is now a fiction that hides the drift.

### 🟠 Finding A4 — Security hardening backed by evidence

- **CORS wildcard** — `app/adapters/api.py:415`. *USA marks `SEC-017` (CORS is not a
  wildcard) as ✅ PASS — that is a **false negative**; the literal `allow_origins=["*"]` is at
  line 415. The automation missed it; this is exactly the 30% the judgement layer exists for.*
- **Bind + reload** — `app/main.py:121` binds `0.0.0.0` with `reload=True`. Bind `127.0.0.1`
  for development and never ship `reload=True`.
- **No auth on any API route** — see A1. The MVP bar in the USA report itself names
  "input validation and output encoding on every user-facing path"; an unauthenticated
  arbitrary-execution route fails that bar outright.

### 🟡 Finding A5 — Governance debt

- **`main` protection unverifiable** — `gh api .../branches/main/protection` returns
  HTTP 403: *"Upgrade to GitHub Pro or make this repository public."* The repo is private
  (`docs/650-workspace-operations.md:26` records PRIVATE / All-Rights-Reserved). Branch
  protection therefore **cannot be confirmed via API** — `IMPLEMENTATION-PLAN.md` §2b asserts
  it is operational without evidence.
- **No `LICENSE`** at root, while `docs/650-workspace-operations.md` documents the repo as
  "All-Rights-Reserved". The absence is *consistent* with ARR, but there is no file stating
  it. USA `REPO-005`.
- **`SECURITY.md` absent** — USA `REPO-009`, the top item in its Sprint 0.
- **`.env.example` absent** while `.env` exists with 8 provider keys
  (`SINGULARITY_API_KEY`, `OPENROUTER_API_KEY`, `NVIDIA_NIM_API_KEY`, `GOOGLE_API_KEY`,
  `GROQ_API_KEY`, `CEREBRAS_API_KEY`, `BLUESMIND_API_KEY`, `BLUESMIND_BASE_URL`). USA `REPO-006`.
  (Confirmed the live `.env` is *not* committed — USA `REPO-002` ✅ is correct.)
- **No committed lockfile at root.** Note the nuance: `frontend/pnpm-lock.yaml` **does** exist,
  so USA `SUP-001` is only half-right — the Python side has none, and USA `SUP-002`
  (frozen-lockfile installs in CI) genuinely cannot be satisfied for Python.

### 🟢 Finding A6 — USA false positives I could disprove (do not "fix" these)

- **`SEC-025` "Adaptive password hashing is present where auth exists" — NOT APPLICABLE.**
  `grep -rn 'password|bcrypt|argon2|jwt' app/` returns a single unrelated hit in a telemetry
  redaction list (`app/telemetry/exporter.py:214`). PROFESSOR-J has **no password
  authentication**; it authenticates to *upstream providers* with API keys. There is nothing
  to hash. The real defect is the opposite one — see A1.
- **`PY-007` "Subprocess calls do not use shell=True" — FALSE POSITIVE.** The flagged
  occurrence at `app/skills/builtin.py:320` is a *comment* explaining that the call is safe:
  *"cmd is an explicit arg LIST (never shell=True), so it is not vulnerable…"*. The actual call
  at `app/skills/builtin.py:322` passes a list and carries `# nosec B603`.
- **`SEC-003` "No plaintext HTTP endpoints"** — all three hits are non-issues:
  `app/skills/builtin.py:1525` is an XML *namespace URI* (`http://www.w3.org/2005/Atom`, not a
  request); `docker/observability.yml:54` and `docker/otel-collector-config.yaml:20` are
  container-internal compose-network names (`http://clickhouse:8123`, `http://langfuse:3000`).
  Route-to-fix: none required; optionally document the internal-TLS decision.
- **`ARCH-003` "god files"** — real but bounded: `app/adapters/api.py` (953 lines) and
  `app/skills/builtin.py` (2159 lines). Downgraded to LOW by the MVP profile. Legitimate
  maintainability debt; `builtin.py` at 2159 lines is worth splitting when next touched.

### 🟢 Finding A7 — Branch hygiene

`task/phase-0.6-governance-hardening` is **not** a candidate to merge: it is 7 commits ahead
of its own base but **152 commits behind `main`**, and its diff against `main` is
**255 deletions / 43 modifications** (i.e. it would delete ~255 files, mostly tests). It dates
from 2026-08-25. It is stale work that should be pruned or explicitly abandoned rather than
resurrected. `feat/lh-integration` and `task/ecc-pilot-2-codex` are likewise unmerged.

### 🟡 Finding A8 — Three BLOCK rules were enforced by "review", and review did not catch them

`docs/RULES.md:17–19` declares an "Import check in review" as the enforcement mechanism for
all three BLOCK rules that Finding A1 breaches. A1 has evidently been in the tree across
many merges and CI runs. **A BLOCK rule enforced only by human attention is not enforced** —
and CI, which does run, checks neither.

This is the highest-leverage *systemic* finding after A1: the fix is not just to gate the
route, but to add a mechanical check (e.g. an import/AST assertion that no web adapter can
call a registered skill without passing `SafetyPolicy.check`, wired into the CI security job
alongside gitleaks and bandit at `.github/workflows/ci.yml:64–90`).

### ⚠️ Note A9 — Two findings require an owner decision, which `AGENTS.md` §8 requires me to escalate rather than resolve

`AGENTS.md` §8 is explicit:

> If a conflict arises between subagent recommendations, tooling, or architectural layers
> that cannot be resolved by the authority hierarchy, **stop, flag the conflict, and request
> human decision**. Do not guess or silently override governance.

Findings **A2(a)** (does the umbrella `authority/` tree exist?) and **A3** (who co-releases
the STEMMA→PROFESSOR-J contract, and to which version?) are exactly this class: each is a
Level-1/L2 governance conflict, and neither can be settled from inside this repository.
They are therefore **flagged, not fixed**, and are put to the owner in §5.

---

## 4. Reconciliation with USA (69.4/100)

I accept the tool's score as a fair MVP reading, with these judgement adjustments:

| USA item | USA verdict | My verdict | Basis |
|---|---|---|---|
| `SEC-017` CORS not wildcard | ✅ PASS | **🔴 WRONG** | `app/adapters/api.py:415` |
| `SEC-025` adaptive password hashing | 🚫 MISSING (HIGH) | **N/A** | no password auth exists |
| `PY-007` no `shell=True` | 🔴 FAIL (HIGH) | **✅ FALSE POSITIVE** | flagged text is a comment |
| `SEC-003` plaintext HTTP | 🔴 FAIL (HIGH) | **🟢 N/A** | namespace URI + internal compose names |
| `SUP-001` lockfile committed | 🚫 MISSING | **🟡 PARTIAL** | `frontend/pnpm-lock.yaml` exists |
| Tool says nothing about the ungated skill route | — | **🔴 CRITICAL (A1)** | `app/adapters/api.py:878` |

**The single most important limitation of the deterministic pass:** it scored security 7.2/10
and flagged *zero* critical issues, while the most consequential defect in the repository —
an unauthenticated, ungated arbitrary-execution endpoint — is invisible to pattern matching
because every individual line of it looks normal. That is the judgement layer's entire reason
for existing.

---

## 5. The next step — a decision, then a sequence

### The blocker is a decision, not a task

Findings A2(a) and A3 cannot be fixed by an agent acting alone, because each requires a
Level-1/L2 owner call:

1. **Does the umbrella `authority/` tree exist at `/home/sajan/Projects/authority/`, or are
   the 8 authority tests asserting a fabric that was never agreed?** (A2a)
2. **Who co-releases the STEMMA→PROFESSOR-J contract — and to which version?** STEMMA
   publishes `2.2.0` and already registers PROFESSOR-J as a consumer; PROFESSOR-J still
   demands `0.1` and `generated_at`. (A3)

Everything else is mechanical.

### Recommended SPRINT 0 — restore a green, safe baseline (do this first)

Ordered so that each step is verifiable by the repo's own commands:

1. **A1 — route the skill endpoint through the gate or remove it.** Either register builtin
   skills into the blessed `ToolExecutor` (`app/bootstrap.py:135`, gated at
   `app/tools/executor.py:332`) and have `/api/skills/execute` dispatch through it, or delete
   the route until it can be gated. Then add a caller-auth dependency to the app.
   *Verify:* a request to the route without credentials is rejected; a `filesystem delete`
   request requires HITL approval.
2. **A4 — bind `127.0.0.1`, drop `reload=True`, restrict CORS to the frontend origin.**
   `app/main.py:121`, `app/adapters/api.py:415`.
3. **A2(c) — fix the voice test assertion** (`tests/unit/voice/test_voice.py`).
4. **A6 note — do not action the three USA false positives.**
5. **Re-run the repo's own verification** and report it honestly:
   `.venv/bin/python -m pytest tests/ && .venv/bin/mypy app/ && .venv/bin/pre-commit run --all-files`
   (currently ruff fails with 79 errors + `E402` — that is step 6, not a blocker to 1–4).
6. **Clear ruff to zero** so `scripts/verify.py` can pass end-to-end for the first time.
7. **A8 — make the BLOCK rules mechanical.** Add a CI check that fails if any web adapter can
   reach a registered skill without passing `SafetyPolicy.check`, and register it in the
   security job at `.github/workflows/ci.yml:64–90`. Without this, A1 can silently recur.

### SPRINT 1 — the two owner decisions (escalated per `AGENTS.md` §8)

8. **Resolve the STEMMA contract co-release** (A3): update
   `app/knowledge/lhs_adapter.py:43–44` to the agreed versions, replace the `generated_at`
   requirement with `content_hash` per STEMMA ADR-0022, **replace the fixture** so it can no
   longer hide the drift, and record the co-release. This is gate G-A per STEMMA ADR-0019.
9. **Resolve the umbrella authority question** (A2a), then either create the workspace tree or
   correct the tests — and add `authority/` to `WORKSPACE-GOVERNANCE.md` if it is real.

### SPRINT 2 — cheap governance wins

10. `SECURITY.md`, `.env.example` (8 vars, placeholders), a root `LICENSE` stating
    All-Rights-Reserved, and the `docs/650` staleness fixes (`verify_governance.py` is cited but
    absent; the repo table needs `STEMMA` and must drop `LearningHubSTEM`).
11. Confirm branch protection in the GitHub UI (API cannot report it on a private Free plan) —
    then correct or remove the `IMPLEMENTATION-PLAN.md` §2b claim.

### Explicitly NOT next

- **Do not** pursue the USA "SPRINT 2 / BACKLOG" security-ceremony items (SLSA provenance,
  Sigstore, VSA, CODEOWNERS, mutation testing). The USA report itself places these at
  LOW/FUTURE for the MVP profile, and scope discipline puts them at **LATER**.
- **Do not** implement the "genuinely external-infra" list in `IMPLEMENTATION-PLAN.md` §2b
  (Docker+gVisor, PostgreSQL+Alembic, ChromaDB/Qdrant dense retrieval, WebRTC) until CI is
  green — building on a red baseline just adds more unverified surface.
- **Do not** merge `task/phase-0.6-governance-hardening` (A7).

---

## 6. Scope classification of this document

- **NOW:** Findings A1, A2, A4 — restore a green and safe baseline.
- **SEAM:** the STEMMA consumer contract (A3) — it is a contract, so it gets versioned and
  co-released rather than patched ad hoc.
- **LATER:** USA LOW/FUTURE supply-chain ceremony, god-file splitting, i18n, e2e/contract-test
  layouts.
- **OUT OF SCOPE:** none introduced by this audit — no dependency, service, or coupling was
  added.

---

*Raw deterministic report: `/tmp/PJ-AUDIT-USA-v226.md` (USA v2.26.0; the global `usa` binary
is v2.8.2 and should be upgraded — it under-reports on this repo).*

**Audit hygiene.** This audit was read-only against the repository: no source, test, or
documentation file was modified. `pre-commit run --all-files` did apply autofixes during
investigation (4 files reformatted, plus end-of-file fixes across 19 files); these were
reverted with `git checkout -- .` and the worktree was verified clean at `de7864f`
(`git status --porcelain` → 0 entries) before this document was written. This report is the
only new file, and it is left **uncommitted** — per `AGENTS.md` §6 all work lands on a branch,
so committing it (e.g. `docs/audit-2026-09-30`) is the owner's call.*
