# Learning Objectives

> Companion: `education-learning-objectives` v0.1.0 from ProjectTemplates 0.1.0
> Answers here are this project's source of truth.
> Re-generate or adopt a newer template only as a deliberate decision (`tpl update`).

---

**Learning objectives written as observable outcomes (what the learner can do at the end).**

By the end of a PROFESSOR-J tutoring session, the learner can:

- **Recall:** state the definition of a target concept (e.g. Newton's second law) and its
  canonical equation, with citation.
- **Apply:** solve a diagnostic problem that requires applying the concept (e.g. compute
  acceleration from F = m·a).
- **Analyze:** identify the misconception that led to an incorrect step and correct it.
- **Create:** derive a related result step-by-step (e.g. derive units, rearrange for a
  different variable).

**Grouped by mastery level.** Recall → Apply → Analyze → Create, per Bloom's taxonomy,
with the system advancing difficulty as mastery metrics improve.

**Alignment: how each objective is assessed.** Formative diagnostic quizzes per objective;
step-level evaluation by `EvaluatorAgent` (SymPy-verified steps); mastery tracked in
`DatabaseEngine`.

**Explicit non-objectives.** This experience does not teach arbitrary ungrounded topics as
fact, does not replace classroom instruction, and does not grade formal summative exams
unless configured for a curriculum.

**Measurable signal that an objective has been achieved.** The learner solves the target
diagnostic problem independently, and mastery state advances past the prerequisite
threshold for that concept.