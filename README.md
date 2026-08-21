# 🤖 PROFESSOR-J — Autonomous AI Platform

> **General-Purpose AI OS with Specialized Knowledge Consumption**
> **Status:** Active Inception & Development
> **Ecosystem Role:** Independent Peer Repository · General-Purpose AI Platform

---

## 🌟 What is PROFESSOR-J?

**PROFESSOR-J is a general-purpose autonomous AI platform** — an AI OS that inherits the
proven JARVIS capability surface (cognitive brain, multi-provider model pool with circuit
breakers, hybrid memory, tiered safety gates, tool sandbox, session/workspace management,
FastAPI + Next.js UI) under a new name, and extends it beyond any single domain.

It is **not bound to LearningHubSTEM**. It consumes LearningHubSTEM as one specialized
knowledge source among others via a consumer adapter, and falls back to general knowledge
where no canonical entity exists.

- 🧠 **JARVIS-class Cognitive Brain** — Intent Analyzer → Task Planner → Execution Runner →
  Response Synthesizer, inherited and hardened from JARVIS.
- 🎓 **Autonomous AI Professor** — Socratic & adaptive tutoring, misconception diagnosis,
  with source provenance from LearningHubSTEM where available.
- 🔬 **Research Companion** — scientific paper ingestion (PDF/OCR), page-exact citation
  provenance, LaTeX proof validation.
- 🧮 **Executable Code & Math Sandbox** — isolated Python execution, SymPy derivations,
  Plotly visualizations, behind tiered safety gates.
- 🎙️ **Voice & Streaming Workspace** — WebRTC voice classroom, SSE token streaming,
  KaTeX rendering.
- ⚡ **Resilient Model Pool** — multi-provider LLM routing with 3-state circuit breakers.
- 💾 **Hybrid Memory** — ChromaDB dense + BM25 sparse retrieval.
- 🛡️ **Tiered Safety Guardrails** — `@safety_gate` (`SAFE` / `SENSITIVE` / `DESTRUCTIVE`)
  with human-in-the-loop approvals.

**General by default, specialized on demand:** tutoring and research are primary domains,
but PROFESSOR-J is a general-purpose personal AI platform, not limited to LearningHubSTEM
or to education.

---

## 🏗️ Architecture at a Glance

```text
PROFESSOR-J/
├── AGENTS.md                  ← Operating rules & governance for developers/AIs
├── PRD.md                     ← Product Requirements Document
├── ARCHITECTURE.md            ← Living system architecture
├── ARCHITECTURE-ESSENTIALS.md ← Quick-reference architectural cheat sheet
├── IMPLEMENTATION-PLAN.md     ← Phased engineering roadmap (Phases 0–9)
├── docs/                      ← Governance, standards & Project Operating System modules
│   ├── GOVERNANCE.md          ← Level-2 governance & authority routing
│   ├── CONSTITUTION.md        ← Development constitution (non-negotiables)
│   ├── RULES.md               ← Enforceable rules
│   ├── STANDARDS.md           ← Coding, docs & working standards
│   ├── PRINCIPLES.md          ← Project values
│   ├── WORKING-PROCEDURE.md   ← How work gets done
│   └── foundation modules      ← Project Operating System foundation answers
│
├── app/                       ← Python Backend Core
│   ├── brain/                 ← Cognitive Engine (Professor, Research, Evaluator, Tool)
│   ├── domain/                ← Pure Python 3.11+ Dataclasses (Zero external deps)
│   ├── knowledge/             ← LearningHubSTEM Consumer Adapter (+ general knowledge)
│   ├── memory/                ← Hybrid ChromaDB Vector + BM25 Retrieval
│   ├── guardrails/            ← @safety_gate Tiered Security Policies
│   ├── models/ & resources/   ← Multi-Provider Router & Circuit Breakers
│   ├── session/ & workspace/  ← Session & workspace management (from JARVIS)
│   └── adapters/              ← FastAPI REST, SSE Streaming & WebRTC Signaling
│
└── frontend/                  ← Next.js 15 Interactive Canvas & Voice UI
```

---

## 🚀 Getting Started

### 1. Backend Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Frontend Setup
```bash
cd frontend
pnpm install
pnpm dev
```

### 3. Verification
```bash
.venv/bin/python -m pytest tests/    # Python test suite
.venv/bin/mypy app/                  # strict typecheck
cd frontend && pnpm typecheck && pnpm lint
```

---

## 🧭 Related Ecosystem Projects

- **[LearningHubSTEM]** — canonical STEM knowledge foundation (consumed via adapter).
- **JARVIS** — the predecessor platform; PROFESSOR-J inherits its capabilities under a new
  name and extends them. JARVIS remains an independent, maintained peer.

[LearningHubSTEM]: /home/sajan/Projects/LearningHubSTEM

---

## 📜 Governance

Read **[`AGENTS.md`]**, **[`docs/GOVERNANCE.md`]**, and **[`docs/ARCHITECTURE-ESSENTIALS.md`]**
before contributing.

[`AGENTS.md`]: AGENTS.md
[`docs/GOVERNANCE.md`]: docs/GOVERNANCE.md
[`docs/ARCHITECTURE-ESSENTIALS.md`]: ARCHITECTURE-ESSENTIALS.md
