# STEM-TUITION Content-Batch Workflow (for PROFESSOR-J)

> Captures the exact, repeated loop used to author and ship narrative lessons. Follow it
> verbatim when asked to continue STEM-TUITION content production. This is the process
> skill — the "what gets done multiple times" the user asked to preserve.

**Target:** add `NarrativeContent` lessons for canonically-present concepts, in batches,
then ship them through the same merge→deploy loop.

---

## The batch loop (one batch = one PR)

**Engine-first:** every authored narrative is a `narrative-lesson` artifact that must pass the
content-engine's `produce()` hard gates; a narrative that is not engine-publishable is **not
accepted**. This is enforced durably by the "engine-gate" test per batch in
`packages/content-engine/tests/engine-gate-batchN.test.ts` (it routes each artifact through
`produce()` and asserts `publish`), so narration never goes through a side-channel manual loop.

1. **Ground.** Read `apps/shell/src/data/knowledge.json` for the target concept's canonical
   fields (`definition`, `common_misconceptions`, `learning_objectives`,
   `real_world_applications`, `relationships`). Never invent or rewrite canonical facts.

2. **Author** a new `apps/shell/src/data/narratives-batchN.ts` exporting
   `export const NARRATIVES_BATCHN: Record<string, NarrativeContent>`, with one mastered
   entry per concept. Shape required by `packages/content-provider/src/narrative.ts`:
   `conceptId`, `hook`, `history`, `figures[]` (name/lifespan/role/contribution/statement/
   statementSource), `timeline[]` (period/event/figure/note), `perspectives[]`
   (figure/view/standing/note), `deepDive` (phenomenon/intro + `rungs[]` starting at
   `Curious`), `whatCameBefore`, `connections[]`, `applications[]`, `workedExamples[]`,
   `analogies[]`, `misconceptions[]`, `tryThis`, `funFacts[]`, `estimatedTimeMinutes`.
   This authoring maps onto the engine's `FormatGenerator` seam for the `narrative-lesson`
   format.

3. **Run it under the engine.** Add (or extend) the **engine-gate test**
   `packages/content-engine/tests/engine-gate-batchN.test.ts`: import the new batch (relative
   path to the shell data), and for each artifact build a `ContentRequest` (`format:
   'narrative-lesson'`, `requiredConcepts: [conceptId]`), call `produce()` with a `generate`
   callback returning that artifact, and **assert `action === 'publish'`**. This drives the
   engine's deterministic schema + coverage hard gates via the narrative-lesson format's
   `validate`/`coverage` hooks. Fix any narrative that holds/rejects before proceeding.

4. **Wire** the new batch into `apps/shell/src/data/narratives.ts` (add the dynamic import +
   spread into `NARRATIVES`; note narrations are code-split via `getNarratives()` per batch —
   the data ships as one chunk per batch file so the size gate is already satisfied).

5. **Bump the integration floor** — `apps/shell/tests/narrative-integration.test.ts`:
   `expect(narrated.length).toBeGreaterThanOrEqual(N)` where N = prior floor + batch size.
   Also update the "narrated+" count in
   `docs/guides/task-playbooks/narration/README.md`.

6. **Verify.**
   ```bash
   cd STEM-TUITION
   pnpm --filter=@stem-tuition/content-engine test   # runs the engine-gate batchN test
   pnpm --filter=@stem-tuition/shell typecheck
   pnpm --filter=@stem-tuition/shell test
   pnpm verify-governance        # must be exit 0
   pnpm docs:sync                # must be exit 0 (pre-commit hook also enforces)
   ```

7. **Ship** (autonomous, Conventional Commits, lowercase subject, scope in the allowed
   commitlint list — `shell` is allowed):
   - `git checkout -b feat/narrative-batch-N`
   - `git add -A && git commit -m "feat(shell): add <domain> narratives"`
   - `git push -u origin feat/narrative-batch-N`
   - `gh pr create --base main --head feat/narrative-batch-N --title "feat(shell): ..."`
   - poll the PR's `Verify governance` check (LOOP until SUCCESS)
   - `gh pr merge N --merge`
   - poll `CI` on `main` until `completed success`
   - verify deploy: `curl -s -o /dev/null -w "%{http_code}" https://stem-tution.pages.dev/learn` (200)
     and confirm the live `learn` bundle + new `narratives-batchN` chunk resolve 200.

8. **Sync local main** and record the new narrated count in this folder's `current-state.md`.

---

## Engineering gotchas (learned the hard way)

- **commitlint**: subject must be **sentence-case/lowercase** and ≤72 chars; scope must be in
  the `scope-enum` whitelist (`.commitlintrc.json`). Adding a new package requires adding its
  name to that whitelist.
- **exactOptionalPropertyTypes**: never assign an optional field `undefined`; use conditional
  spreads (`...(x ? { x } : {})`). Lifecycle on every batch.
- **code-split / size budget**: `bundlesize.config.json` gates each built asset at 100 kB gzip.
  All 6+ narrative batch files are separate chunks via `getNarratives()` dynamic import; do NOT
  statically import all batches into one module or the `learn` bundle exceeds the budget.
- **docs:sync** registers new packages in `.phase.json` (a human-gate decision — put content
  packages under Phase 8). Missing `ARCHITECTURE.toml` fails `verify-registry`.
- **stale typescript**: hoisted TS is pinned to `^5.9.3`; package-local `tsc` may resolve TS7
  via pnpm — put test files in `tests/` (not `src/`) so `tsc` (which `include`s only `src`)
  avoids the `@types/chai` ↔ vitest `containSubset` conflict.
- **environment**: multi-agent pipelining (`workflow tool agent()`, `subagent`) returns `null`
  here — author directly to the rubric. Re-probe before relying on parallel agents.
