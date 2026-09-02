# Skill: stem-tuition-content-developer

> PROFESSOR-J capability definition for developing STEM-TUITION educational content
> (the repeated narrative-batching loop). Machine-loaded into `SkillRegistry`
> (`app/skills/registry.py`) or read by an agent; `data:` block mirrors `SkillMetadata`.
> Authoritative process lives in `../stem-tuition/workflow.md`.

```yaml
name: stem-tuition-content-developer
description: Author and ship STEM-TUITION narrative lessons in batches, end to end
  (ground → author → wire → verify → PR → merge → deploy) via the documented batch loop.
version: 1.0.0
author: PROFESSOR-J
category: content-production
tags: [stem-tuition, content, narratives, batch, pedagogy, education, typescript]
requires_approval: true
timeout_seconds: 3600
```

## When to use

Use whenever asked to:
- add, extend, or master a **narrative lesson** for a STEM concept in STEM-TUITION;
- continue the "batch-N" content-production loop (e.g. physics Grade-12 completeness);
- update the narrated-concepts count / playbook floor / live bundle.

This is the recurring, high-frequency job the user wants preserved so the work is
repeatable without re-deriving the process.

## Responsibilities

1. **Ground** in canonical LHS (`apps/shell/src/data/knowledge.json`) — compose with the
   entity, never rewrite canonical facts.
2. **Author** a mastered `NarrativeContent` per concept: hook, dated history, real figures
   with recorded words + sources, timeline, respected/differing views, scaling deep-dive
   (Curious → Nerd), worked numeric examples, analogies, misconceptions, try-this, fun-facts.
3. **Wire + verify** against the strict TS conventions and the governance gate
   (`pnpm verify-governance`), then **ship** via the autonomous branch → PR → merge →
   deploy-verify loop.
4. **Report** the new narrated count and update `agents_dev/stem-tuition/current-state.md`.

## Procedure

1. `cd STEM-TUITION`; read `AGENTS.md`, `docs/CONSTITUTION.md`, and
   `/home/sajan/Projects/PROFESSOR-J/agents_dev/stem-tuition/current-state.md` + `workflow.md`.
2. Pick the next unnarrated concept (see the remaining-physics queues).
3. Author `narratives-batchN.ts`; wire into `narratives.ts`; bump the test floor.
4. `pnpm --filter=@stem-tuition/shell typecheck && pnpm --filter=@stem-tuition/shell test`
   then `pnpm verify-governance` (exit 0) and `pnpm docs:sync`.
5. Branch → commit (lowercase subject, allowed scope) → push → PR → poll `Verify governance`
   → merge on green → poll CI → verify live bundle 200.
6. Sync local main; update the current-state brief.

## Outputs

- A merged, deployed batch of `NarrativeContent` lessons on STEM-TUITION `main`.
- An updated narrated-concepts floor and a refreshed `current-state.md`.

## Verification

- `cd STEM-TUITION && pnpm verify-governance` exits 0.
- `pnpm docs:sync` exits 0.
- Live `/learn` and the new `narratives-batchN` chunk resolve HTTP 200.

## References

- Process: `agents_dev/stem-tuition/workflow.md`
- Engine/architecture: `../stem-tuition/current-state.md`; `docs/architecture/content-production-engine-v2.md` (in STEM-TUITION)
- Narrative shape: `packages/content-provider/src/narrative.ts` (in STEM-TUITION)
