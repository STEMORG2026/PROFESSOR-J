# Assessment & Evaluation

> Companion: `education-assessment-evaluation` v0.1.0 from ProjectTemplates 0.1.0
> Answers here are this project's source of truth.
> Re-generate or adopt a newer template only as a deliberate decision (`tpl update`).

---

**Formative and summative assessments, each mapped to an objective.**

- Formative: diagnostic quizzes and step-level feedback map 1:1 to objectives
  (`docs/204-education-learning-objectives.md`).
- Summative: end-of-topic mastery checks; completion of an objective's quiz at threshold.

**Grading or mastery criteria, and how fairness is maintained.**

Mastery is a score per concept (e.g. via Bayesian Knowledge Tracing / IRT) with explicit
thresholds. Fairness: same criteria for all learners; hints recorded; partial credit for
correct intermediate steps.

**Feedback: what, when, and from whom.**

- What: step-level correctness + misconception-specific hints + grounded references.
- When: immediate per step (EvaluatorAgent), plus periodic summary.
- From: the system; optionally a configured human educator.

**How the experience itself is evaluated.**

- Learner outcomes (resolution rate, mastery gains) collected via telemetry.
- Session quality (Socratic ratio, hint effectiveness) reviewed periodically.
- Triggers improvement: results below the ≥85% resolution target → tune scaffolding.

**Evidence that real learning occurred.**

Learners solve target problems independently that they could not at session start; mastery
scores advance; retention re-checks pass.
