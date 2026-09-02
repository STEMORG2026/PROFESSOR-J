# Skill: stem-tuition-content-engine

> PROFESSOR-J capability definition for extending the STEM-TUITION general-purpose
> content-production engine (architecture v2). Machine-loaded into `SkillRegistry`
> (`app/skills/registry.py`) or read by an agent; `data:` block mirrors `SkillMetadata`.
> The authoritative type contracts live in `packages/content-engine/src/` (in STEM-TUITION).

```yaml
name: stem-tuition-content-engine
description: Extend and use the STEM-TUITION content-production engine seam — request
  model, declarative format specs, hard-gate verification, and intent/essence checks
  (architecture v2, ADR-016).
version: 1.0.0
author: PROFESSOR-J
category: content-production
tags: [stem-tuition, content-engine, format-spec, verification, architecture, typescript]
requires_approval: true
timeout_seconds: 1800
```

## When to use

Use whenever asked to:
- add a **new content format** (`quiz`, `lab-script`, `animation-spec`, …) to STEM-TUITION;
- extend the **request model / blueprint / verification seam**;
- understand why STEM-TUITION content is produced the way it is (hard gates, format specs,
  no average-score gate).

## Core invariants to preserve

1. **Request-driven, not assumption-driven.** `ContentRequest` carries only `topic` + `intent`
   as required; grade, subject, curriculum, language, format, level are optional request data.
   Never "invent" a grade/format the request did not supply.
2. **Formats are declarative.** A new format = a `FormatSpec` registered in `FormatRegistry`
   (+ a `FormatGenerator` + `FormatValidator`). No `if story / if textbook` branches in core.
   Each spec may declare deterministic `coverage(payload)` and `validate(payload)` hooks so
   coverage + schema gates are format-agnostic (narrative → `conceptId`; quiz → question
   concept links + question shape; no hook → generic required-component presence). A format
   is never a free pass.
3. **Hard-gate publication.** `evaluateGates` requires EVERY gate PASS. A single FAIL blocks
   publication no matter the other scores. Scores are diagnostic only.
4. **Intent/essence is separate from facts.** `INTENT_ESSENCE_VERIFIER` checks "did the artifact
   accomplish what was intended as an experience?", independent of factual correctness.
5. **Targeted repair.** `routeRepair`/`repairOrders` map a failed gate to the stage that caused
   it; only a genuinely wrong plan forces whole-artifact regeneration.
6. **LHS boundary.** The engine composes with canonical LHS; external research never overwrites
   an LHS fact in place — it may raise a `canonical-review-signal`.

## Package map (in STEM-TUITION)

| File | Content |
|---|---|
| `packages/content-engine/src/request.ts` | `ContentRequest` (optional-heavy) |
| `packages/content-engine/src/formats.ts` | `FormatSpec`, `FormatRegistry`, `narrative-lesson` + `quiz`, `Artifact` |
| `packages/content-engine/src/blueprint.ts` | `Blueprint`, `planFromRequest`, `resolveFormats` |
| `packages/content-engine/src/verification.ts` | `evaluateGates`, deterministic validators, `INTENT_ESSENCE_VERIFIER`, `routeRepair`/`repairOrders` |
| `packages/content-engine/src/pipeline.ts` | **`produce()`** — the request-driven pipeline runner (Blueprint → generate → verify → repair → publish/hold/reject) |
| `packages/content-engine/tests/` | 49 tests (23 core + 25 stress + 1 engine-gate), all passing |

## Engine-gated narration (the single content path)

STEM-TUITION narration runs **through the engine**, not a manual loop. Each batch has an
`engine-gate-batchN.test.ts` that imports the batch's artifacts and, for every one, builds a
`ContentRequest` (`format: 'narrative-lesson'`, `requiredConcepts: [conceptId]`), calls
`produce()` with a `generate` callback returning that artifact, and **asserts `action ===
'publish'`**. This drives the narrative-lesson format's `validate` + `coverage` hooks — the
deterministic schema + coverage hard gates — so a narrative that loses a required section or is
keyed to the wrong concept is rejected. To author content: add the narrative to the batch, add
(extend) the engine-gate test, bump the integration floor, wire into `getNarratives()`. See
`agents_dev/stem-tuition/workflow.md`.

## Running the engine (`produce`, migration N4)

The engine is `LLM-agnostic`: `FormatGenerator` and `SemanticVerifier` are injected
callbacks, so `produce()` runs testably without a network, and a real runner
(workflow/litellm/…) supplies those callbacks:

```ts
import { FormatRegistry, produce } from '@stem-tuition/content-engine';

const decision = await produce(
  request,                                   // ContentRequest (topic + intent minimum)
  { registry: new FormatRegistry(),          // narrative-lesson + quiz by default
    callbacks: { generate, verify },         // injected LLM seams
    maxRepairRounds: 2 },
  context,                                   // KnowledgeContext (canonical LHS grounding)
);
// decision.action: 'publish' | 'hold' | 'reject', with blueprint, artifact, report.
```

The runner applies deterministic gates (coverage, schema) natively and semantic gates
(factual, lhs-fidelity, pedagogical, format, intent-essence) via the injected verifier,
then routes failures to targeted repair (`repairOrders`). Only a truly wrong plan forces
whole-artifact regeneration.

## To add a new format

```ts
registry.register({
  id: 'lab-script',
  name: 'Laboratory activity',
  description: '…',
  components: [{ id: 'aim', kind: 'text', required: true }],
  validation: { rules: ['components.aim must be non-empty'], semanticCriteria: [] },
  outputSchema: 'LabScript',
  generationGuidance: ['…'],
});
```
No core change. Add a `FormatGenerator` (LLM) and, to keep deterministic gates honest, the
optional declarative hooks — `coverage(payload)` (which concept ids the artifact covers) and
`validate(payload)` (deterministic schema findings; else a required-component check applies):

```ts
registry.register({
  id: 'lab-script',
  name: 'Laboratory activity',
  components: [{ id: 'aim', kind: 'text', required: true }],
  validation: { rules: ['components.aim must be non-empty'], semanticCriteria: [] },
  outputSchema: 'LabScript',
  coverage: (p) => (p.conceptId ? [String(p.conceptId)] : []),
  validate: (p) => (p.aim ? [] : ['aim required']),
});
```

## Verification

- `cd STEM-TUITION && pnpm --filter=@stem-tuition/content-engine typecheck`
- `pnpm --filter=@stem-tuition/content-engine test` (48 pass: 23 core + 25 stress; add tests for any new format/runner path)
- `pnpm --filter=@stem-tuition/content-engine test:coverage` (≈98% lines)
- `pnpm verify-governance` exits 0 (incl. `lint:registry` — new packages need
  `ARCHITECTURE.toml` and `.phase.json` registration).

## Stress suite

`packages/content-engine/tests/engine-stress.test.ts` (25 tests) adversarially exercises the
production engine: the architecture review §O 12 radically-different requests, boundary /
invalid inputs, repair-loop exhaustion (bounded, exact, never infinite), malformed artifacts
caught deterministically, deterministic-vs-LLM gate separation (a deterministic FAIL can never
be masked), and custom declarative formats driving the core end to end. Add a case here when
you change the pipeline or a format's coverage/validate logic.

## References

- Full review: `docs/architecture/content-production-engine-v2.md` (in STEM-TUITION)
- Decision: `docs/ADR/016-content-engine.md` (in STEM-TUITION; migration N4–N6 landed 2026-09-02)
- v1 narration playbook is now **deprecated** and is only a reference for the
  `narrative-lesson` format; `scripts/narrate/` is deprecated (superseded by `produce()`).
