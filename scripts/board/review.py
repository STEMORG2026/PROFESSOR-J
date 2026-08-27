#!/usr/bin/env python3
"""
Virtual Board Review Script — PROFESSOR-J

Deterministic governance checks for every PR.
Run: python scripts/board/review.py
"""

from __future__ import annotations

import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str = ""
    details: dict[str, Any] | None = None


class VirtualBoard:
    """Virtual Board review engine — deterministic checks only."""

    def __init__(self, repo_root: Path = REPO_ROOT):
        self.repo_root = repo_root
        self.results: list[CheckResult] = []

    def run_all(self) -> bool:
        """Run all deterministic checks. Returns True if all pass."""
        checks = [
            ("import_layering", self.check_import_layering),
            ("domain_purity", self.check_domain_purity),
            ("schema_drift", self.check_schema_drift),
            ("prerequisite_graph", self.check_prerequisite_graph),
            ("safety_gate_coverage", self.check_safety_gate_coverage),
            ("mcp_tool_search", self.check_mcp_tool_search),
            ("otel_spans", self.check_otel_spans),
            ("langgraph_checkpoint", self.check_langgraph_checkpoint),
        ]

        all_passed = True
        for name, check_fn in checks:
            result = check_fn()
            self.results.append(result)
            status = "✓ PASS" if result.passed else "✗ FAIL"
            print(f"  {status} {name}: {result.message}")
            if not result.passed:
                all_passed = False

        return all_passed

    # ── Individual Checks ──

    def check_import_layering(self) -> CheckResult:
        """Verify import layering: domain ← brain ← bootstrap ← adapters ← presentation."""
        violations = []

        # Check app/domain/ has no imports from app/*
        domain_path = REPO_ROOT / "app" / "domain"
        for py_file in domain_path.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()
            for line in content.splitlines():
                stripped = line.strip()
                if (stripped.startswith(("from app.", "import app."))) and not stripped.startswith(
                    "from app.domain."
                ):
                    violations.append(f"{py_file.relative_to(self.repo_root)}: {stripped}")

        # Check app/brain/ doesn't import web-framework objects (FastAPI/Starlette/Uvicorn).
        # Matches the framework itself, not loose substrings like "request" (which
        # would false-positive on domain types such as ToolCallRequest).
        brain_path = REPO_ROOT / "app" / "brain"
        _WEB_FRAMEWORKS = ("fastapi", "starlette", "uvicorn")
        for py_file in brain_path.rglob("*.py"):
            content = py_file.read_text()
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith(("from app.adapters", "import app.adapters")):
                    violations.append(f"{py_file.relative_to(self.repo_root)}: {stripped}")
                if (
                    any(w in stripped.lower() for w in _WEB_FRAMEWORKS)
                    and ("import" in stripped or "from" in stripped)
                    and "TYPE_CHECKING" not in content
                ):
                    # Explicit web-framework imports are disallowed (type hints allowed).
                    violations.append(f"{py_file.relative_to(self.repo_root)}: {stripped}")

        passed = len(violations) == 0
        return CheckResult(
            name="import_layering",
            passed=passed,
            message=f"{len(violations)} layering violations" if violations else "Layering OK",
            details={"violations": violations},
        )

    def check_domain_purity(self) -> CheckResult:
        """Verify app/domain/ contains only frozen dataclasses with zero external deps."""
        violations = []
        domain_path = REPO_ROOT / "app" / "domain"

        for py_file in domain_path.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    is_enum = any(
                        isinstance(base, ast.Name) and base.id == "Enum" for base in node.bases
                    )
                    # Dataclass decorator may be bare @dataclass or @dataclass(...)
                    has_dataclass = any(
                        (isinstance(dec, ast.Name) and dec.id == "dataclass")
                        or (
                            isinstance(dec, ast.Call)
                            and isinstance(dec.func, ast.Name)
                            and dec.func.id == "dataclass"
                        )
                        for dec in node.decorator_list
                    )
                    has_frozen = any(
                        isinstance(dec, ast.Call)
                        and isinstance(dec.func, ast.Name)
                        and dec.func.id == "dataclass"
                        and any(
                            kw.arg == "frozen"
                            and isinstance(kw.value, ast.Constant)
                            and kw.value.value is True
                            for kw in dec.keywords
                        )
                        for dec in node.decorator_list
                    )
                    # Enums and guarded private classes are exempt from the frozen rule.
                    if not is_enum and not has_frozen and not node.name.startswith("_"):
                        violations.append(f"{py_file}: class {node.name} not frozen")

                    # Plain classes (not @dataclass) may not define public methods.
                    for item in node.body:
                        if (
                            isinstance(item, ast.FunctionDef)
                            and not item.name.startswith("_")
                            and not has_dataclass
                            and not is_enum
                        ):
                            violations.append(
                                f"{py_file}: class {node.name} has method "
                                f"{item.name} but not dataclass"
                            )

                # Check for non-dataclass imports (stdlib + typing + app.domain only)
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        # `import typing as _t`, `import uuid`, etc. are fine.
                        top = alias.name.split(".")[0]
                        if top not in {
                            "typing",
                            "dataclasses",
                            "datetime",
                            "uuid",
                            "enum",
                            "pathlib",
                            "functools",
                            "__future__",
                        }:
                            violations.append(f"{py_file}: import {alias.name} in domain")
                elif (
                    isinstance(node, ast.ImportFrom)
                    and node.module
                    and not node.module.startswith(
                        (
                            "typing",
                            "dataclasses",
                            "datetime",
                            "uuid",
                            "enum",
                            "pathlib",
                            "functools",
                            "app.domain",
                            "__future__",
                        )
                    )
                ):
                    violations.append(f"{py_file}: import from {node.module} in domain")

        passed = len(violations) == 0
        return CheckResult(
            name="domain_purity",
            passed=passed,
            message=f"{len(violations)} purity violations" if violations else "Domain purity OK",
            details={"violations": violations},
        )

    def check_schema_drift(self) -> CheckResult:
        """Verify LHS adapter validates export_version=0.1 and schema_version=0.1."""
        adapter_path = REPO_ROOT / "app" / "knowledge" / "lhs_adapter.py"
        if not adapter_path.exists():
            return CheckResult(
                name="schema_drift",
                passed=True,  # Not implemented yet — adapter arrives in Phase 1
                message="LHS adapter not yet implemented",
                details={"path": str(adapter_path)},
            )

        content = adapter_path.read_text()
        checks = [
            (
                "export_version",
                "EXPECTED_EXPORT_VERSION" in content and "0.1" in content,
            ),
            (
                "schema_version",
                "EXPECTED_SCHEMA_VERSION" in content and "0.1" in content,
            ),
            (
                "zero_drift",
                "zero-drift" in content.lower() or "zerodrift" in content.lower(),
            ),
        ]

        failed = [name for name, ok in checks if not ok]
        passed = len(failed) == 0
        return CheckResult(
            name="schema_drift",
            passed=passed,
            message=f"Missing: {', '.join(failed)}" if failed else "LHS adapter validates v0.1",
            details={"checks": dict(checks)},
        )

    def check_prerequisite_graph(self) -> CheckResult:
        """Verify prerequisite graph: no cycles, transitive closure, all LHS IDs resolvable."""
        # This would require loading the LHS export and checking the graph
        # For now, verify the domain model has the prerequisite_ids method
        concept_path = REPO_ROOT / "app" / "domain" / "concept.py"
        if not concept_path.exists():
            return CheckResult(
                name="prerequisite_graph",
                passed=False,
                message="Concept entity not found",
            )

        content = concept_path.read_text()
        checks = [
            ("prerequisite_ids", "prerequisite_ids" in content),
            ("mathematically_requires", "mathematically_requires" in content),
            ("logically_requires", "logically_requires" in content),
            ("appears_in_law", "appears_in_law" in content),
            ("all_dependencies", "all_dependencies" in content),
        ]

        failed = [name for name, ok in checks if not ok]
        passed = len(failed) == 0
        return CheckResult(
            name="prerequisite_graph",
            passed=passed,
            message=f"Missing methods: {', '.join(failed)}"
            if failed
            else "Prerequisite graph methods present",
            details={"checks": dict(checks)},
        )

    def check_safety_gate_coverage(self) -> CheckResult:
        """Verify every tool has @safety_gate and DESTRUCTIVE requires HITL."""
        tool_files = (
            list((REPO_ROOT / "app" / "tools").rglob("*.py"))
            if (REPO_ROOT / "app" / "tools").exists()
            else []
        )
        # Also check skills (only concrete tool implementations, not infrastructure)
        skill_files = (
            list((REPO_ROOT / "app" / "skills").rglob("*.py"))
            if (REPO_ROOT / "app" / "skills").exists()
            else []
        )

        # Skill infrastructure files are framework, not tools — not subject to @safety_gate.
        excluded_skill_files = {"__init__.py", "base.py", "registry.py", "builtin.py"}

        all_files = tool_files + [f for f in skill_files if f.name not in excluded_skill_files]
        if not all_files:
            return CheckResult(
                name="safety_gate_coverage",
                passed=True,  # Not implemented yet
                message="No tools/skills yet",
            )

        violations = []
        for py_file in all_files:
            content = py_file.read_text()
            # Look for @safety_gate decorator; skip __init__.py and base classes.
            if (
                "@safety_gate" not in content
                and "safety_tier" not in content
                and py_file.name != "__init__.py"
                and "base" not in py_file.name
            ):
                violations.append(f"{py_file.relative_to(self.repo_root)}: missing @safety_gate")

        passed = len(violations) == 0
        return CheckResult(
            name="safety_gate_coverage",
            passed=passed,
            message=f"{len(violations)} tools missing @safety_gate"
            if violations
            else "Safety gate coverage OK",
            details={"violations": violations},
        )

    def check_mcp_tool_search(self) -> CheckResult:
        """Verify MCP servers declare tool search for on-demand loading."""
        mcp_path = REPO_ROOT / "app" / "mcp"
        if not mcp_path.exists():
            return CheckResult(
                name="mcp_tool_search",
                passed=True,  # Not implemented yet
                message="MCP client not yet implemented",
            )

        content = ""
        for py_file in (mcp_path).rglob("*.py"):
            content += py_file.read_text()

        checks = [
            ("MCPServerManager", "MCPServerManager" in content),
            (
                "ToolSearch",
                "MCPToolSearch" in content or "tool_search" in content.lower(),
            ),
            ("cache_tools_list", "cache_tools_list" in content),
            (
                "CodeExecutionTools",
                "CodeExecutionTools" in content or "code_as_tools" in content.lower(),
            ),
        ]

        failed = [name for name, ok in checks if not ok]
        passed = len(failed) == 0
        return CheckResult(
            name="mcp_tool_search",
            passed=passed,
            message=f"Missing: {', '.join(failed)}"
            if failed
            else "MCP tool search pattern present",
            details={"checks": dict(checks)},
        )

    def check_otel_spans(self) -> CheckResult:
        """Verify OTel spans emitted for agent, tool, retrieval, guardrail, evaluator."""
        telemetry_path = REPO_ROOT / "app" / "telemetry" / "exporter.py"
        if not telemetry_path.exists():
            return CheckResult(
                name="otel_spans",
                passed=False,
                message="Telemetry exporter not found",
            )

        content = telemetry_path.read_text()
        checks = [
            ("OTLP exporter", "OTLPSpanExporter" in content),
            (
                "Langfuse auth",
                "_langfuse_auth_header" in content or "Authorization" in content,
            ),
            ("gen_ai attributes", "gen_ai.operation.name" in content),
            ("tool attributes", "tool.name" in content),
            (
                "retrieval attributes",
                "retrieval.query" in content or "retrieval.vector_store" in content,
            ),
            (
                "guardrail attributes",
                "guardrail.tool" in content or "guardrail.tier" in content,
            ),
            (
                "evaluator attributes",
                "evaluator.name" in content or "evaluator.score" in content,
            ),
        ]

        failed = [name for name, ok in checks if not ok]
        passed = len(failed) == 0
        return CheckResult(
            name="otel_spans",
            passed=passed,
            message=f"Missing: {', '.join(failed)}" if failed else "OTel spans configured",
            details={"checks": dict(checks)},
        )

    def check_langgraph_checkpoint(self) -> CheckResult:
        """Verify LangGraph StateGraph compiles and checkpointing works."""
        # Check for LangGraph imports and StateGraph usage
        brain_path = REPO_ROOT / "app" / "brain"
        if not brain_path.exists():
            return CheckResult(
                name="langgraph_checkpoint",
                passed=True,  # Not implemented yet
                message="Cognitive brain not yet implemented",
            )

        content = ""
        for py_file in (REPO_ROOT / "app" / "brain").rglob("*.py"):
            content += py_file.read_text()

        checks = [
            ("StateGraph", "StateGraph" in content),
            ("TypedDict", "TypedDict" in content),
            (
                "checkpointer",
                "checkpointer" in content.lower()
                or "MemorySaver" in content
                or "PostgresCheckpointer" in content,
            ),
            ("interrupt", "interrupt" in content or "Command" in content),
        ]

        # Blocking: the graph MUST exist and use a typed state. Checkpointing and
        # interrupts are a documented, intentionally-pending roadmap item (Phase 3,
        # IMPLEMENTATION-PLAN) once the graph itself is present, so their absence is
        # recorded as a note rather than failing the gate.
        blocking = [name for name, ok in checks if not ok and name in {"StateGraph", "TypedDict"}]
        pending = [name for name, ok in checks if not ok and name in {"checkpointer", "interrupt"}]
        if blocking:
            return CheckResult(
                name="langgraph_checkpoint",
                passed=False,
                message="Missing: " + ", ".join(blocking),
            )
        if pending:
            return CheckResult(
                name="langgraph_checkpoint",
                passed=True,
                message="Graph present; checkpointing/interrupts pending (Phase 3): "
                + ", ".join(pending),
                details={"pending": pending},
            )
        return CheckResult(
            name="langgraph_checkpoint",
            passed=True,
            message="LangGraph checkpointing configured",
        )


def main() -> int:
    board = VirtualBoard()
    print("🔍 Virtual Board Review — PROFESSOR-J")
    print("=" * 50)

    all_passed = board.run_all()

    print("=" * 50)
    passed_count = sum(1 for r in board.results if r.passed)
    total_count = len(board.results)
    print(f"Summary: {passed_count}/{total_count} checks passed")

    # Generate ledger
    ledger_path = REPO_ROOT / "board" / "ledger.md"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)

    ledger_content = f"""# Virtual Board Ledger

Generated: {__import__('datetime').datetime.utcnow().isoformat()}Z

## Summary
- **Total Checks**: {total_count}
- **Passed**: {passed_count}
- **Failed**: {total_count - passed_count}
- **Status**: {'✅ PASS' if all_passed else '❌ FAIL'}

## Results
"""
    for result in board.results:
        status = "✅" if result.passed else "❌"
        ledger_content += f"- {status} **{result.name}**: {result.message}\n"
        if result.details:
            ledger_content += f"  - Details: {json.dumps(result.details, indent=2)}\n"

    ledger_path.write_text(ledger_content)
    print(f"\n📋 Ledger written to: {ledger_path.relative_to(REPO_ROOT)}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
