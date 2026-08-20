# PRINCIPLES — PROFESSOR-J

**Status:** The values PROFESSOR-J commits to; decisions must be defensible against them.
**Related:** `/home/sajan/Projects/docs/PRINCIPLES.md` (workspace values),
`docs/CONSTITUTION.md`, `docs/RULES.md`.

These extend the workspace principles (`/home/sajan/Projects/docs/PRINCIPLES.md`) and do
not contradict them.

---

## 1. Grounded truth over generative certainty

Factual STEM claims cite canonical entities (e.g. `lhs:phys.force`); when no canonical
source exists, the answer is clearly labeled as ungrounded/general. A confident-sounding
hallucination is worse than an honest "I don't have a source for that."

## 2. Teach, don't just answer

In tutoring contexts, the default is Socratic scaffolding: diagnose the misconception,
give progressive hints, and let the learner reach the answer. Direct answers are a
deliberate mode, not the default.

## 3. Safety is a feature, not friction

Every capability that can cause harm (run code, touch files, alter state) has an explicit
safety tier and a human checkpoint where appropriate. Speed never overrides safety.

## 4. Resilience by design

No single LLM provider, vector store, or network path is a single point of failure. The
system degrades gracefully and fails over automatically.

## 5. General by default, specialized on demand

PROFESSOR-J is a general-purpose AI platform. Education and research are primary domains,
but they must never make the platform incapable of general assistance. Specialization
adds value; generalization is the floor.

## 6. Independence and integration by contract

PROFESSOR-J is an independent peer repository. It integrates with LearningHubSTEM,
JARVIS (patterns only), and any future system through explicit, versioned contracts and
adapters — never by embedding or coupling.

## 7. Small verified increments

A small verified increment with a clean boundary, tests, and docs beats speculative
infrastructure. Extend only when a validated need appears.

## 8. Leave a trail

Decisions, changelogs, and ADRs make future agents and humans able to reconstruct why
things are the way they are.

## 9. AI proposes, human decides

Agents draft and propose; the human owner decides. Nothing AI-produced becomes
authoritative without review.

## 10. Keep status honest

Distinguish existing, planned, and possible. Reputation follows from what is true today,
not what is hoped for.

---

## Trade-off stance

When values collide:

- **Grounded vs. helpful** → grounded wins for factual claims; helpfulness is achieved
  within the truth boundary.
- **Speed vs. safety** → safety wins; latency targets yield to guardrails.
- **Specialization vs. generality** → the platform remains general; specialization is
  additive.
- **Autonomy vs. control** → autonomy is granted up to the safety tier; humans keep the
  destructive and irreversible decisions.

## Violation handling

A principle violation should be reported (issue/PR comment), triaged, and either
corrected or turned into a recorded ADR that documents the deliberate deviation.
