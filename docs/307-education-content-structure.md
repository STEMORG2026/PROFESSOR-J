# Content Structure

> Companion: `education-content-structure` v0.1.0 from ProjectTemplates 0.1.0
> Answers here are this project's source of truth.
> Re-generate or adopt a newer template only as a deliberate decision (`tpl update`).

---

**Content units and their internal structure.**

A content unit follows: **Objective → Explanation (grounded) → Worked Example → Practice →
Check.** Each unit references canonical LearningHubSTEM entity IDs; equations render in
LaTeX.

**Formats/media used and why.**

- Text + LaTeX (KaTeX) — precise, searchable.
- Interactive graphs (Plotly/D3) — visualize relationships.
- Voice (WebRTC) — natural spoken explanations.
- Sandboxed code/SymPy — runnable verification.
A single explanation may be shared across units via reference, not duplication.

**How content is versioned and who may change it.**

Content units are versioned with the repo; changes require a PR under `docs/STANDARDS.md`.
Canonical knowledge is never edited in PROFESSOR-J — only referenced (contract with
LearningHubSTEM).

**Accessibility.**

Plain-English defaults for beginners; alternative media (text/audio); WCAG-minded UI;
keyboard navigation; screen-reader basics.

**Relationship of this content to shared knowledge assets.**

All canonical definitions, equations, and prerequisite edges are **referenced** from
LearningHubSTEM exports; PROFESSOR-J stores only derived indexes, caches, and
pedagogical scaffolding around them.