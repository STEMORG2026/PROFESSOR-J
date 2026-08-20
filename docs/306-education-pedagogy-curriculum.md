# Pedagogy & Curriculum

> Companion: `education-pedagogy-curriculum` v0.1.0 from ProjectTemplates 0.1.0
> Answers here are this project's source of truth.
> Re-generate or adopt a newer template only as a deliberate decision (`tpl update`).

---

**Pedagogical approach and why it fits these learners.**

**Socratic scaffolding** as the default: diagnose the learner's current understanding,
present progressively harder hints, and let the learner reach the answer. Direct
explanation is available as an explicit mode (`Expository Lecture`) but is not the default.
This fits learners because it builds durable understanding and confidence, not just
transient answers. Adaptive difficulty tunes problem complexity to mastery metrics.

**External curriculum or syllabus alignment.**

Target curricula: SEE / NEB (Nepal), A-Levels, undergraduate STEM, plus mappings toward
CBSE, GCSE, NGSS, IB as LATER. The authority deciding sequence is the LearningHubSTEM
prerequisite graph, optionally overlaid with a curriculum standard when configured.

**Sequencing rationale.**

Prerequisite-first: the system will not advance a learner to `lhs:phys.force` until
`lhs:phys.mass` and `lhs:phys.acceleration` mastery thresholds are met. This mirrors the
canonical concept graph and prevents compounding gaps.

**Activity, practice, and feedback strategy per objective.**

- Recall → definitional Q&A with citation.
- Apply → diagnostic problems with step-by-step SymPy-verified feedback.
- Analyze → misconception-targeted prompts.
- Create → derivation exercises with EvaluatorAgent checking each step.
- Formative assessment quizzes map one-to-one to objectives.

**What is intentionally left to the learner vs supplied.**

The learner supplies reasoning and intermediate steps; the system supplies scaffolding,
verification, and grounded references. The final insight is always the learner's.
