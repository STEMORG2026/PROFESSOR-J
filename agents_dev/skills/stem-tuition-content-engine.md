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
| `packages/content-engine/tests/` | 23 tests, all passing |

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
No core change. Then add a `FormatGenerator` (LLM) and run the deterministic
`FormatValidator` + hard-gate verifiers.

## Verification

- `cd STEM-TUITION && pnpm --filter=@stem-tuition/content-engine typecheck`
- `pnpm --filter=@stem-tuition/content-engine test` (23 pass; add tests for any new format/runner path)
- `pnpm verify-governance` exits 0 (incl. `lint:registry` — new packages need
  `ARCHITECTURE.toml` and `.phase.json` registration).

## References

- Full review: `docs/architecture/content-production-engine-v2.md` (in STEM-TUITION)
- Decision: `docs/ADR/016-content-engine.md` (in STEM-TUITION; migration N4–N6 landed 2026-09-02)
- v1 narration playbook is now **deprecated** and is only a reference for the
  `narrative-lesson` format; `scripts/narrate/` is deprecated (superseded by `produce()`).
