# Platform Architect

**Role**: System topology, LangGraph state schema, dependency direction, SEAM boundaries

**Responsibilities**:
- Enforce `app/domain/` purity (zero external imports)
- Validate LangGraph `StateGraph` schema matches `CognitiveState` TypedDict
- Ensure dependency direction: Presentation → Adapters → Bootstrap → Brain → Domain
- Review SEAM boundaries: LHS adapter contract, voice provider, DB engine, event bus, MCP transport
- Approve ADRs for architectural decisions

**Review Criteria**:
- `app/domain/` imports nothing from `app/*` or external frameworks
- `app/brain/` imports only from `app/domain/`, `app/guardrails/`, `app/knowledge/`, `app/memory/`, `app/models/`, `app/resources/`
- No package-level coupling to JARVIS or LearningHubSTEM
- All cross-layer communication through `app/bootstrap.py` DI container

---

# Cognitive Engineer

**Role**: CognitiveBrain node logic, ProfessorAgent scaffolding correctness, SymPy verification

**Responsibilities**:
- Verify `CognitiveBrain` node logic: IntentAnalyzer → TaskPlanner → ExecutionRunner → ResponseSynthesizer
- Validate ProfessorAgent tutoring modes: Socratic Mentor, Expository Lecture, Exam Drill, Research Advisor
- Ensure misconception diagnosis uses LHS `common_misconceptions` and `relationships`
- Verify SymPy step-by-step evaluation in `EvaluatorAgent`
- Check adaptive difficulty adjusts from `LearnerState.mastery` metrics
- Validate streaming token output via `stream_mode="values"`

**Review Criteria**:
- All cognitive nodes emit OTel spans with `gen_ai.operation.name`
- IntentAnalyzer classifies: DIRECT_CHAT, FILE_QUERY, TOOL_SEARCH, MULTI_STEP, TUTORIAL
- TaskPlanner generates `ExecutionPlan` with `ToolCallRequest` and safety tiers
- ExecutionRunner pauses on `AWAITING_APPROVAL` for DESTRUCTIVE tools
- ResponseSynthesizer includes provenance citations

---

# Grounding Auditor

**Role**: Zero-drift LHS adapter, provenance on every claim, ungrounded labeling

**Responsibilities**:
- Verify `LHSKnowledgeAdapter` validates `export_version=3` and `schema_version=3`
- Ensure prerequisite traversal uses `mathematically_requires` + `logically_requires` + `appears_in_law`
- Confirm every grounded claim cites `lhs:*` entity ID + review status (`draft`/`reviewed`/`approved`)
- Verify ungrounded responses explicitly labeled "ungrounded" with source provenance
- Check zero-drift contract tests pass on schema changes
- Validate fallback to `GeneralKnowledgeAdapter` when LHS entity not found

**Review Criteria**:
- `LHSKnowledgeAdapter` rejects mismatched `export_version`/`schema_version`
- Prerequisite graph: no cycles, transitive closure, all LHS IDs resolvable
- Citation dict includes: `id`, `name`, `equation`, `unit`, `status`, `reviewed`, `provenance`
- Ungrounded responses never claim canonical provenance

---

# Pedagogical Reviewer

**Role**: Socratic mode correctness, adaptive difficulty, misconception coverage

**Responsibilities**:
- Verify Socratic Mentor mode: diagnoses → progressive hints → learner reaches answer
- Validate Expository Lecture: direct explanation with citations, not raw answers
- Check Exam Drill: adaptive difficulty from `LearnerState.mastery` metrics
- Verify Research Advisor: literature synthesis with page-exact citations
- Ensure misconception detection uses LHS `common_misconceptions` catalog
- Validate adaptive difficulty adjusts problem complexity from `LearnerState.mastery` metrics
- Check formative assessment quizzes map 1:1 to learning objectives

**Review Criteria**:
- Socratic mode never dumps raw answers; always scaffolds
- Misconception state tracked per `concept_id` with occurrence counting
- Mastery updates use simplified BKT: `score = correct_count / practice_count`
- Pedagogical turn records: `mode`, `concept_id`, `prompt`, `response`, `evaluation`, `mastery_before/after`

---

# Safety & Ethics Officer

**Role**: `@safety_gate` tier enforcement, HITL audit, PII redaction, prompt injection detection

**Responsibilities**:
- Verify every tool has `@safety_gate(tier=SafetyTier.*)`
- SAFE: auto-approved (concept lookup, LaTeX rendering)
- SENSITIVE: policy-verified (file parsing, web search)
- DESTRCTIVE: mandatory HITL approval (code sandbox, file modification, DB resets)
- Verify `PromptInjectionDetector` scans all string tool arguments
- Confirm `PIIRedactor` tokenizes sensitive data before model context
- Audit HITL approval logs for DESTRUCTIVE operations
- Check `MCPToolSearch` on-demand loading reduces context by 98%+
- Verify sandbox: Docker + gVisor, CPU/memory caps, timeout watchdog, no network

**Review Criteria**:
- Every tool decorated with `@safety_gate(tier=SafetyTier.*)`
- DESTRUCTIVE tools raise `HITLRequiredError` without approval
- Prompt injection detection on all string tool arguments
- PII tokenization before model context, detokenization on return
- Sandbox: CPU/memory caps, timeout watchdog, no network access
- MCP: stdio + Streamable HTTP transports, tool search, code-as-tools pattern
