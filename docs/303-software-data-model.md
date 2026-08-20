# Data Model

> Companion: `software-data-model` v0.1.0 from ProjectTemplates 0.1.0
> Answers here are this project's source of truth.
> Re-generate or adopt a newer template only as a deliberate decision (`tpl update`).

---

## Core entities and their relationships

| Entity | Fields (representative) | Relates to |
|--------|-------------------------|------------|
| `ConceptEntity` | id (`lhs:*`), definition, equations, prerequisites | prerequisite graph edges |
| `LearnerState` | learner_id, mastery map (concept → score), history | ConceptEntity |
| `PedagogicalTurn` | turn_id, learner_id, mode, prompt, response, eval | LearnerState, ConceptEntity |
| `MisconceptionState` | learner_id, concept_id, detected misconception | LearnerState |
| `ExecutionPlan` | plan_id, steps, status (`AWAITING_APPROVAL`, …) | ToolCallRequest |
| `ToolCallRequest` | tool, args, safety_tier, approval_state | ExecutionPlan |
| `Session` | session_id, user_id, context window | transcript |
| `Conversation` | messages with roles + provenance | Session |
| `MasteryScore` | learner_id, concept_id, score, updated_at | LearnerState |

## Integrity rules & ownership

- Domain entities live in `app/domain/` (pure dataclasses); ownership of each entity's
  lifecycle is documented in code.
- A concept's canonical truth lives in LearningHubSTEM; PROFESSOR-J stores only derived
  indexes and caches (regenerable).

## Storage technology & where data resides

- **SQLite** locally (profiles, transcripts, mastery) → **PostgreSQL** in production.
- **ChromaDB** for vectors (derived, regenerable).
- Learner data is stored locally first; production requires explicit owner decision.

## Migration & evolution

- DB schema carries `user_version`; migrations are additive and non-breaking.
- Indexes (Chroma) are rebuildable from canonical source.

## Retention, deletion & privacy

- Transcripts retained per owner policy; deletion supported per learner.
- No PII in telemetry/analytics; no secrets in data stores.
