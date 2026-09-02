# STEM-TUITION Content Production — PROFESSOR-J Working Folder

> **Purpose:** This folder is PROFESSOR-J's dedicated workspace seam for developing
> STEM-TUITION content and the content-production engine. When asked to continue
> STEM-TUITION content work, read this brief first, then the linked governance, then
> follow `workflow.md`. This is advisory knowledge, not authority — STEM-TUITION's own
> governance is authoritative inside that repo (see `../docs/GOVERNANCE.md`).

**Last updated:** 2026-09-02 (live brief — refresh from the repo before relying on it)

---

## Where things live (authoritative)

| Concern | Path | Note |
|---|---|---|
| STEM-TUITION repo | `/home/sajan/Projects/STEM-TUITION` | independent peer repo (turborepo) |
| Canonical knowledge (LHS export) | `apps/shell/src/data/knowledge.json` | 112 `LhsEntity` objects; **source of canonical facts** |
| Authored narratives | `apps/shell/src/data/narratives-batch1..6.ts` + `getNarratives()` in `narratives.ts` | consumer-owned pedagogy (CONSTITUTION.md §35) |
| Narrative model + composer | `packages/content-provider/src/narrative.ts` (`NarrativeContent`, `composeNarrativeLesson`) | application model, not canonical |
| Lesson builder | `apps/shell/src/lib/lesson-builder.ts` (`buildLessons(entities, narratives)`) | pure; code-split |
| Content-engine seam (v2) | `packages/content-engine/` | request model, format specs, hard-gate verification |
| Curriculum mappings | `apps/shell/src/data/curriculum-mappings.ts` | grades 8–12; NEB Grade 11–12 mappings |
| Narration playbook (narrative format) | `docs/guides/task-playbooks/narration/` | reference for the `narrative-lesson` format |
| Architecture v2 review | `docs/architecture/content-production-engine-v2.md` | the engine redesign this folder supports |
| Key decisions | `docs/ADR/016-content-engine.md` | general-purpose content-engine seam |

## Current state (progress snapshot)

- **Physics concepts: 57 of 79 narrated** (narrative-lesson format), live and deployed.
  Batch-7 (merged PR #33, `a9e68d9`) added `vector`, `scalar`, `projectile-motion`,
  `gravitation`, `gravitational-acceleration`, `weight`, `temperature`, `thermal-energy`,
  `change-of-state`, `electromagnetic-spectrum`. Integration floor: 57.
- **Remaining unnarrated physics** for Grade-12 completeness: mechanics (`motion`, `speed`,
  `measurement`, `physical-quantity`, `distance`/`displacement`, `graphical-analysis`,
  `mechanical-advantage`, `energy-loss`, `our-environment`, `application-of-mechanics`, …),
  modern/nuclear (`nuclear-fission`, `nuclear-fusion`, `energy-sources`,
  `nuclear-reactor`/related), plus `electron`, `current`, `resistance`, `circuit`, … — see
  `docs/architecture/content-production-engine-v2.md` and the batch queues.
- **Content engine COMPLETE (N1–N6)** merged in `packages/content-engine/`: the seam
  (`ContentRequest`/`Blueprint`/`FormatSpec`/hard-gate verification) **plus** the request-driven
  pipeline runner `produce()` (Blueprint → generate → verify → repair → publish/hold/reject;
  LLM-agnostic via injected `FormatGenerator`/`SemanticVerifier` callbacks) **plus** a second
  non-narrative `quiz` FormatSpec. The v1 narration playbook is deprecated (reference for the
  `narrative-lesson` format only); `scripts/narrate/` is deprecated. A production
  workflow/litellm runner attachment over these seams is the remaining step (ADR-016 N4-next).
- **Environment constraint:** the multi-agent pipeline (`workflow tool agent()`,
  `subagent`) returns `null` in this harness — PROFESSOR-J currently authors narratives
  **directly to the rubric** rather than via parallel agents. Re-probe before assuming
  agents are available.

## How to continue content work

1. `cd STEM-TUITION`; read `AGENTS.md` + `docs/CONSTITUTION.md` + this brief.
2. Follow `workflow.md` for the exact per-batch loop.
3. Author missing narratives in a fresh `apps/shell/src/data/narratives-batchN.ts`;
   bump the integration floor in `apps/shell/tests/narrative-integration.test.ts`;
   wire into `narratives.ts`; run `pnpm verify-governance`; `pnpm docs:sync`; branch →
   PR → merge on CI-green → verify the deploy bundle.
4. Respect the hard gates of `packages/content-engine` when working on the engine itself.
