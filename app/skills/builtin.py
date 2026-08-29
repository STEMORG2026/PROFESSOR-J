"""Built-in Skills — Core skills for PROFESSOR-J Phase 1."""

from __future__ import annotations

import json
import logging
import subprocess  # nosec B404 - used only by the git skill with explicit list args (no shell)
from pathlib import Path
from typing import Any

from app.knowledge.lhs_adapter import LHSKnowledgeAdapter
from app.skills.base import Skill, SkillMetadata, SkillResult
from app.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)


# ── Filesystem Skill ────────────────────────────────────────────────


class FilesystemSkill(Skill[dict[str, Any]]):
    """Filesystem operations via internal implementation (supplements MCP)."""

    def _default_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="filesystem",
            description="Read, write, list, and manipulate files in the workspace",
            version="1.0.0",
            category="filesystem",
            tags=["filesystem", "io", "workspace"],
            timeout_seconds=10,
            requires_approval=False,
            parameters_schema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["read", "write", "list", "exists", "delete", "mkdir"],
                        "description": "Filesystem operation to perform",
                    },
                    "path": {"type": "string", "description": "File or directory path"},
                    "content": {
                        "type": "string",
                        "description": "Content to write (for write operation)",
                    },
                    "recursive": {
                        "type": "boolean",
                        "default": False,
                        "description": "Recursive operation",
                    },
                },
                "required": ["operation", "path"],
            },
            returns_schema={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "content": {"type": "string"},
                    "entries": {"type": "array", "items": {"type": "string"}},
                    "error": {"type": "string"},
                },
            },
        )

    def validate_params(self, **kwargs: Any) -> bool:
        op = kwargs.get("operation")
        return op in {"read", "write", "list", "exists", "delete", "mkdir"}

    async def execute(self, **kwargs: Any) -> SkillResult[dict[str, Any]]:
        operation = kwargs["operation"]
        path = Path(kwargs["path"])

        try:
            if operation == "read":
                if not path.exists():
                    return SkillResult.failure(f"File not found: {path}")
                content = path.read_text(encoding="utf-8")
                return SkillResult.success({"success": True, "content": content})

            elif operation == "write":
                content = kwargs.get("content", "")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                return SkillResult.success({"success": True})

            elif operation == "list":
                if not path.exists():
                    return SkillResult.failure(f"Directory not found: {path}")
                entries = [str(p.relative_to(path)) for p in path.iterdir()]
                return SkillResult.success({"success": True, "entries": entries})

            elif operation == "exists":
                return SkillResult.success({"success": True, "exists": path.exists()})

            elif operation == "delete":
                if not path.exists():
                    return SkillResult.failure(f"Path not found: {path}")
                if path.is_dir():
                    import shutil

                    shutil.rmtree(path)
                else:
                    path.unlink()
                return SkillResult.success({"success": True})

            elif operation == "mkdir":
                path.mkdir(parents=kwargs.get("recursive", False), exist_ok=True)
                return SkillResult.success({"success": True})

        except Exception as e:
            logger.exception("Filesystem operation failed: %s", e)
            return SkillResult.failure(str(e))

        return SkillResult.failure(f"Unknown operation: {operation}")


# ── Git Skill ──────────────────────────────────────────────────────


class GitSkill(Skill[dict[str, Any]]):
    """Git operations for version control."""

    def _default_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="git",
            description="Git operations (status, diff, log, commit, branch, push, pull)",
            version="1.0.0",
            category="version-control",
            tags=["git", "vcs", "workspace"],
            timeout_seconds=30,
            requires_approval=True,  # Git writes need approval
            parameters_schema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": [
                            "status",
                            "diff",
                            "log",
                            "commit",
                            "branch",
                            "push",
                            "pull",
                            "add",
                        ],
                        "description": "Git operation to perform",
                    },
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": [],
                    },
                    "cwd": {"type": "string", "description": "Working directory"},
                    "message": {
                        "type": "string",
                        "description": "Commit message (for commit)",
                    },
                },
                "required": ["operation"],
            },
            returns_schema={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "output": {"type": "string"},
                    "error": {"type": "string"},
                },
            },
        )

    def validate_params(self, **kwargs: Any) -> bool:
        op = kwargs.get("operation")
        return op in {
            "status",
            "diff",
            "log",
            "commit",
            "branch",
            "push",
            "pull",
            "add",
        }

    async def execute(self, **kwargs: Any) -> SkillResult[dict[str, Any]]:
        operation = kwargs["operation"]
        args = kwargs.get("args", [])
        cwd = kwargs.get("cwd", ".")
        message = kwargs.get("message", "")

        try:
            cmd = ["git", "-C", cwd, operation]
            if operation == "commit":
                if not message:
                    return SkillResult.failure("Commit message required")
                cmd.extend(["-m", message])
            elif operation == "add":
                cmd.extend(args if args else ["."])
            else:
                cmd.extend(args)

            # cmd is an explicit arg LIST (never shell=True), so it is not
            # vulnerable to shell injection despite coming from user params.
            result = subprocess.run(  # nosec B603 - list args, no shell
                cmd, capture_output=True, text=True, timeout=30, cwd=cwd
            )

            if result.returncode == 0:
                return SkillResult.success({"success": True, "output": result.stdout})
            else:
                return SkillResult.failure(result.stderr or f"Git {operation} failed")

        except subprocess.TimeoutExpired:
            return SkillResult.failure("Git operation timed out")
        except Exception as e:
            logger.exception("Git operation failed: %s", e)
            return SkillResult.failure(str(e))


# ── Web Search Skill ──────────────────────────────────────────────


class WebSearchSkill(Skill[dict[str, Any]]):
    """Web search via MCP (requires brave-search server)."""

    def _default_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="web_search",
            description="Search the web for information",
            version="1.0.0",
            category="research",
            tags=["search", "web", "research"],
            timeout_seconds=15,
            requires_approval=False,
            mcp_servers=["brave-search"],
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {
                        "type": "integer",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50,
                    },
                },
                "required": ["query"],
            },
            returns_schema={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "results": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "url": {"type": "string"},
                                "snippet": {"type": "string"},
                            },
                        },
                    },
                    "error": {"type": "string"},
                },
            },
        )

    async def execute(self, **kwargs: Any) -> SkillResult[dict[str, Any]]:
        # Web search requires the MCP brave-search server, which is not yet wired.
        return SkillResult.failure(
            "web_search not implemented: requires MCP brave-search server",
            component="web_search",
            not_implemented=True,
        )


# ── Code Execution Skill ──────────────────────────────────────────


class CodeExecutionSkill(Skill[dict[str, Any]]):
    """Code execution via internal sandbox (supplements MCP python server)."""

    def _default_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="code_execution",
            description="Execute Python code in isolated sandbox with resource limits",
            version="1.0.0",
            category="execution",
            tags=["python", "sandbox", "execution", "code"],
            timeout_seconds=10,
            requires_approval=True,  # DESTRUCTIVE
            parameters_schema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute"},
                    "timeout": {
                        "type": "integer",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 60,
                    },
                    "memory_mb": {
                        "type": "integer",
                        "default": 512,
                        "minimum": 64,
                        "maximum": 2048,
                    },
                },
                "required": ["code"],
            },
            returns_schema={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "stdout": {"type": "string"},
                    "stderr": {"type": "string"},
                    "return_code": {"type": "integer"},
                    "execution_time_ms": {"type": "number"},
                    "error": {"type": "string"},
                },
            },
        )

    async def execute(self, **kwargs: Any) -> SkillResult[dict[str, Any]]:
        # Sandboxed execution requires app/tools/sandbox.py (Phase 5, roadmap).
        # Returning success here would be dangerously wrong for a DESTRUCTIVE tier.
        del kwargs
        return SkillResult.failure(
            "code_execution not implemented: sandbox (app.tools.sandbox) is not built",
            component="code_execution",
            not_implemented=True,
        )


# ── LearningHubSTEM Skill ──────────────────────────────────────────


class LHSTEMSkill(Skill[dict[str, Any]]):
    """Access LearningHubSTEM canonical knowledge via consumer adapter."""

    def _default_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="lhstem_knowledge",
            description="Query LearningHubSTEM canonical concepts, equations, prerequisites",
            version="1.0.0",
            category="knowledge",
            tags=["lhstem", "stem", "physics", "grounding", "canonical"],
            timeout_seconds=5,
            requires_approval=False,
            parameters_schema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": [
                            "get_concept",
                            "get_prerequisites",
                            "search",
                            "has_concept",
                        ],
                        "description": "Operation to perform",
                    },
                    "entity_id": {
                        "type": "string",
                        "description": "LHSTEM entity ID (e.g. lhs:phys.force)",
                    },
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["operation"],
            },
            returns_schema={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "concept": {"type": "object"},
                    "prerequisites": {"type": "array", "items": {"type": "string"}},
                    "results": {"type": "array", "items": {"type": "object"}},
                    "has_concept": {"type": "boolean"},
                    "review_status": {"type": "string"},
                    "error": {"type": "string"},
                },
            },
        )

    def validate_params(self, **kwargs: Any) -> bool:
        op = kwargs.get("operation")
        return op in {"get_concept", "get_prerequisites", "search", "has_concept"}

    def _get_adapter(self) -> LHSKnowledgeAdapter:
        """Lazily construct the canonical knowledge adapter from settings."""
        from app.config.settings import get_settings

        return LHSKnowledgeAdapter(get_settings().lhs_export_path)

    async def execute(self, **kwargs: Any) -> SkillResult[dict[str, Any]]:
        operation = kwargs["operation"]
        entity_id = kwargs.get("entity_id", "")
        query = kwargs.get("query", "")

        try:
            adapter = self._get_adapter()
        except Exception as e:
            return SkillResult.failure(
                f"LHS knowledge adapter unavailable: {e}",
                component="lhstem",
            )

        if operation == "get_concept":
            concept = adapter.get_concept(entity_id) if entity_id else None
            if concept is None:
                return SkillResult.failure(
                    f"Canonical entity not found: {entity_id}",
                    component="lhstem",
                    grounded=False,
                )
            return SkillResult.success(
                {
                    "success": True,
                    "concept": concept.to_citation_dict(),
                    "review_status": concept.status.value,
                    "grounded": concept.is_grounded(),
                },
                component="lhstem",
            )

        if operation == "get_prerequisites":
            prereqs = adapter.get_prerequisites(entity_id) if entity_id else ()
            return SkillResult.success(
                {"success": True, "prerequisites": list(prereqs)},
                component="lhstem",
            )

        if operation == "has_concept":
            if not entity_id:
                return SkillResult.failure("entity_id is required", component="lhstem")
            return SkillResult.success(
                {"success": True, "has_concept": adapter.has_concept(entity_id)},
                component="lhstem",
            )

        if operation == "search":
            if not query:
                return SkillResult.failure("query is required", component="lhstem")
            results = adapter.search_concepts(query, limit=10)
            return SkillResult.success(
                {
                    "success": True,
                    "results": [r.to_citation_dict() for r in results],
                },
                component="lhstem",
            )

        return SkillResult.failure(f"Unknown operation: {operation}", component="lhstem")


# ── Memory Skill ───────────────────────────────────────────────────


class MemorySkill(Skill[dict[str, Any]]):
    """Memory operations (store, retrieve, update, delete) via MemoryService."""

    def _default_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="memory",
            description="Store and retrieve memories (facts, episodes, semantic knowledge)",
            version="1.0.0",
            category="memory",
            tags=["memory", "retrieval", "storage", "episodic", "semantic"],
            timeout_seconds=10,
            requires_approval=False,
            parameters_schema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["store", "retrieve", "update", "delete", "search"],
                        "description": "Memory operation",
                    },
                    "content": {"type": "string", "description": "Memory content"},
                    "category": {"type": "string", "description": "Memory category"},
                    "memory_type": {"type": "string", "description": "Memory type"},
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "default": 10},
                    "memory_id": {
                        "type": "string",
                        "description": "Memory ID for update/delete",
                    },
                },
                "required": ["operation"],
            },
            returns_schema={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "memory_id": {"type": "string"},
                    "memories": {"type": "array", "items": {"type": "object"}},
                    "error": {"type": "string"},
                },
            },
        )

    def validate_params(self, **kwargs: Any) -> bool:
        op = kwargs.get("operation")
        return op in {"store", "retrieve", "update", "delete", "search"}

    async def execute(self, **kwargs: Any) -> SkillResult[dict[str, Any]]:
        # Memory operations require MemoryService (ChromaDB + BM25), not yet built.
        del kwargs
        return SkillResult.failure(
            "memory not implemented: MemoryService is not built",
            component="memory",
            not_implemented=True,
        )


# ── Skill Factory ──────────────────────────────────────────────────

BUILTIN_SKILLS: dict[str, type[Skill[Any]]] = {
    "filesystem": FilesystemSkill,
    "git": GitSkill,
    "web_search": WebSearchSkill,
    "code_execution": CodeExecutionSkill,
    "lhstem_knowledge": LHSTEMSkill,
    "memory": MemorySkill,
}


def create_builtin_skills() -> dict[str, Skill[Any]]:
    """Create instances of all built-in skills."""
    return {name: cls() for name, cls in BUILTIN_SKILLS.items()}


def register_builtin_skills(registry: SkillRegistry) -> int:
    """Register all built-in skills with the registry."""
    registered = 0
    for name, skill_class in BUILTIN_SKILLS.items():
        try:
            skill = skill_class()
            registry.register(skill)
            registered += 1
        except Exception as e:
            logger.error("Failed to register skill %s: %s", name, e)
    return registered


# ── Project Automation Skills ────────────────────────────────────────


class ProjectBuildSkill(Skill[dict[str, Any]]):
    """Build and test project - supports multiple project types."""

    def _default_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="project_build",
            description="Build and test projects (Python, Node.js, Rust, Go, etc.)",
            version="1.0.0",
            category="automation",
            tags=["build", "test", "ci", "automation"],
            timeout_seconds=120,
        )

    def validate_params(self, **kwargs: Any) -> bool:
        op = kwargs.get("operation")
        return op in {"build", "test", "lint", "typecheck", "all"}

    async def execute(self, **kwargs: Any) -> SkillResult[dict[str, Any]]:
        import os
        import subprocess  # nosec B404 - explicit list args, no shell (see skill body)

        operation = kwargs.get("operation", "all")
        project_path = kwargs.get("project_path", ".")
        project_type = kwargs.get("project_type")  # auto-detect if not provided

        # Auto-detect project type
        if not project_type:
            if os.path.exists(os.path.join(project_path, "pyproject.toml")) or os.path.exists(
                os.path.join(project_path, "requirements.txt")
            ):
                project_type = "python"
            elif os.path.exists(os.path.join(project_path, "package.json")):
                project_type = "node"
            elif os.path.exists(os.path.join(project_path, "Cargo.toml")):
                project_type = "rust"
            elif os.path.exists(os.path.join(project_path, "go.mod")):
                project_type = "go"
            else:
                project_type = "unknown"

        commands = {
            "python": {
                "build": ["pip", "install", "-e", "."],
                "test": ["python", "-m", "pytest", "-v"],
                "lint": ["ruff", "check", "."],
                "typecheck": ["mypy", "."],
            },
            "node": {
                "build": ["pnpm", "install"],
                "test": ["pnpm", "test"],
                "lint": ["pnpm", "lint"],
                "typecheck": ["pnpm", "typecheck"],
            },
            "rust": {
                "build": ["cargo", "build"],
                "test": ["cargo", "test"],
                "lint": ["cargo", "clippy"],
                "typecheck": ["cargo", "check"],
            },
            "go": {
                "build": ["go", "build", "./..."],
                "test": ["go", "test", "./..."],
                "lint": ["golangci-lint", "run"],
                "typecheck": ["go", "vet", "./..."],
            },
        }

        if project_type not in commands:
            return SkillResult.failure(
                f"Unknown project type: {project_type}",
                component="project_build",
            )

        ops_to_run = [operation] if operation != "all" else list(commands[project_type].keys())
        results: dict[str, Any] = {}

        for op in ops_to_run:
            if op not in commands[project_type]:
                results[op] = {
                    "status": "skipped",
                    "error": f"Operation '{op}' not supported for {project_type}",
                }
                continue

            cmd = commands[project_type][op]
            try:
                result = subprocess.run(  # nosec B603 - explicit list args, no shell
                    cmd,
                    cwd=project_path,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                results[op] = {
                    "status": "success" if result.returncode == 0 else "failed",
                    "returncode": result.returncode,
                    "stdout": result.stdout[-2000:],  # Last 2000 chars
                    "stderr": result.stderr[-2000:],
                }
            except subprocess.TimeoutExpired:
                results[op] = {
                    "status": "timeout",
                    "error": f"Operation '{op}' timed out after 120s",
                }
            except Exception as e:
                results[op] = {"status": "error", "error": str(e)}

        return SkillResult.success(
            {
                "project_type": project_type,
                "operations": results,
                "project_path": project_path,
            }
        )


class GitExtendedSkill(Skill[dict[str, Any]]):
    """Extended Git operations for project automation."""

    def _default_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="git_extended",
            description="Extended Git operations (branch, commit, push, PR, merge, rebase)",
            version="1.0.0",
            category="automation",
            tags=["git", "version-control", "automation"],
            timeout_seconds=60,
        )

    def validate_params(self, **kwargs: Any) -> bool:
        op = kwargs.get("operation")
        return op in {
            "status",
            "diff",
            "log",
            "branch",
            "checkout",
            "create_branch",
            "commit",
            "push",
            "pull",
            "merge",
            "rebase",
            "stash",
            "remote_add",
            "remote_remove",
            "tag",
            "reset",
        }

    async def execute(self, **kwargs: Any) -> SkillResult[dict[str, Any]]:
        import os
        import subprocess  # nosec B404 - explicit list args, no shell (see skill body)

        operation = kwargs.get("operation")
        repo_path = kwargs.get("repo_path", ".")
        args = kwargs.get("args", [])

        if not os.path.exists(os.path.join(repo_path, ".git")):
            return SkillResult.failure("Not a git repository", component="git_extended")

        commands = {
            "status": ["git", "status", "--porcelain"],
            "diff": ["git", "diff"] + args,
            "log": ["git", "log", "--oneline", "-20"] + args,
            "branch": ["git", "branch", "-a"] + args,
            "checkout": ["git", "checkout"] + args,
            "create_branch": ["git", "checkout", "-b"] + args,
            "commit": ["git", "commit", "-m"] + args,
            "push": ["git", "push"] + args,
            "pull": ["git", "pull"] + args,
            "merge": ["git", "merge"] + args,
            "rebase": ["git", "rebase"] + args,
            "stash": ["git", "stash"] + args,
            "remote_add": ["git", "remote", "add"] + args,
            "remote_remove": ["git", "remote", "remove"] + args,
            "tag": ["git", "tag"] + args,
            "reset": ["git", "reset"] + args,
        }

        if operation not in commands:
            return SkillResult.failure(f"Unknown operation: {operation}", component="git_extended")

        try:
            cmd = commands[operation]
            result = subprocess.run(  # nosec B603 - explicit list args, no shell
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return SkillResult.success(
                {
                    "operation": operation,
                    "status": "success" if result.returncode == 0 else "failed",
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            )
        except subprocess.TimeoutExpired:
            return SkillResult.failure(
                f"Git operation '{operation}' timed out", component="git_extended"
            )
        except Exception as e:
            return SkillResult.failure(str(e), component="git_extended")


class FileTemplateSkill(Skill[dict[str, Any]]):
    """Generate files from templates for project scaffolding."""

    def _default_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="file_template",
            description="Generate files from templates (component, service, test, config, etc.)",
            version="1.0.0",
            category="automation",
            tags=["template", "scaffold", "generate", "automation"],
            timeout_seconds=30,
        )

    def validate_params(self, **kwargs: Any) -> bool:
        op = kwargs.get("operation")
        return op in {"list", "generate", "create_custom"}

    async def execute(self, **kwargs: Any) -> SkillResult[dict[str, Any]]:
        from pathlib import Path

        operation = kwargs.get("operation")
        template_name = kwargs.get("template_name")
        output_path = kwargs.get("output_path", ".")
        variables = kwargs.get("variables", {})

        templates = {
            "python_cli": {
                "description": "Python CLI project with Click",
                "files": {
                    "pyproject.toml": """[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{{project_name}}"
version = "0.1.0"
description = "{{description}}"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "click>=8.0",
    "{{extra_deps}}",
]

[project.optional-dependencies]
dev = ["pytest", "ruff", "mypy", "pre-commit"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 100

[tool.mypy]
strict = true
""",
                    "src/{{project_name}}/cli.py": """import click

@click.group()
@click.version_option()
def main():
    \"\"\"{{description}}\"\"\"
    pass

@main.command()
@click.argument("name")
def hello(name: str):
    \"\"\"Say hello.\"\"\"
    click.echo(f"Hello, {name}!")

if __name__ == "__main__":
    main()
""",
                    "tests/test_cli.py": """from click.testing import CliRunner
from {{project_name}}.cli import main

def test_hello():
    runner = CliRunner()
    result = runner.invoke(main, ["hello", "World"])
    assert result.exit_code == 0
    assert "Hello, World!" in result.output
""",
                },
            },
            "react_component": {
                "description": "React component with TypeScript and tests",
                "files": {
                    "{{component_name}}.tsx": """import React from "react";

interface {{component_name}}Props {
  {{#each props}}
  {{name}}: {{type}};
  {{/each}}
}

export const {{component_name}}: React.FC<{{component_name}}Props> = ({
  {{#each props}}
  {{name}},
  {{/each}}
}) => {
  return (
    <div className="{{class_name}}">
      {{> children}}
    </div>
  );
};
""",
                    "{{component_name}}.test.tsx": (
                        """import { render, screen } from "@testing-library/react";
import { {{component_name}} } from "./{{component_name}}";

describe("{{component_name}}", () => {
  it("renders without crashing", () => {
    render(<{{component_name}} {{#each props}}{{name}}={{default}} {{/each}} />);
    expect(screen.getByRole("{{role}}")).toBeInTheDocument();
  });
});
"""
                    ),
                    "{{component_name}}.stories.tsx": (
                        """import type { Meta, StoryObj } from "@storybook/react";
import { {{component_name}} } from "./{{component_name}}";

const meta: Meta<typeof {{component_name}}> = {
  title: "Components/{{component_name}}",
  component: {{component_name}},
};

export default meta;
type Story = StoryObj<typeof {{component_name}}>;

export const Default: Story = {
  args: {
    {{#each props}}
    {{name}}: {{default}},
    {{/each}}
  },
};
"""
                    ),
                },
            },
            "python_fastapi": {
                "description": "FastAPI service with SQLAlchemy and Pydantic",
                "files": {
                    "pyproject.toml": """[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{{project_name}}"
version = "0.1.0"
description = "{{description}}"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.100",
    "uvicorn>=0.23",
    "sqlalchemy>=2.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
]

[project.optional-dependencies]
dev = ["pytest", "httpx", "ruff", "mypy", "pre-commit"]
""",
                    "src/{{project_name}}/main.py": """from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="{{project_name}}", description="{{description}}")

class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None

@app.get("/")
async def root():
    return {"message": "Welcome to {{project_name}}"}

@app.post("/items/")
async def create_item(item: Item):
    return item
""",
                    "tests/test_main.py": """from fastapi.testclient import TestClient
from {{project_name}}.main import app

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "Welcome to {{project_name}}"
""",
                },
            },
        }

        if operation == "list":
            return SkillResult.success(
                {
                    "templates": {name: info["description"] for name, info in templates.items()},
                }
            )

        if operation == "generate":
            if template_name not in templates:
                return SkillResult.failure(
                    f"Template '{template_name}' not found", component="file_template"
                )

            template: dict[str, Any] = templates[template_name]
            output_dir = Path(output_path)
            output_dir.mkdir(parents=True, exist_ok=True)

            # Simple variable substitution (in real implementation, use Jinja2)
            created_files = []
            for file_path, content in template["files"].items():
                # Defensive: template file bodies must be text; coerce anything
                # else (e.g. a metadata tuple) so substitution cannot crash.
                content = content if isinstance(content, str) else str(content)
                # Substitute variables
                for key, value in variables.items():
                    content = content.replace(f"{{{{{key}}}}}", value)
                content = content.replace(
                    "{{project_name}}", variables.get("project_name", "my_project")
                )
                content = content.replace(
                    "{{description}}", variables.get("description", "A new project")
                )
                content = content.replace("{{extra_deps}}", variables.get("extra_deps", ""))
                content = content.replace(
                    "{{component_name}}", variables.get("component_name", "MyComponent")
                )
                content = content.replace(
                    "{{class_name}}", variables.get("class_name", "my-component")
                )

                # Create parent dirs
                full_path = output_dir / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)
                created_files.append(str(full_path))

            return SkillResult.success(
                {
                    "template": template_name,
                    "created_files": created_files,
                }
            )

        if operation == "create_custom":
            # Save a custom template
            template_content = kwargs.get("template_content")
            if not template_content:
                return SkillResult.failure("template_content required", component="file_template")

            custom_dir = Path(output_path) / ".professor-templates"
            custom_dir.mkdir(parents=True, exist_ok=True)
            (custom_dir / f"{template_name}.json").write_text(template_content)

            return SkillResult.success(
                {
                    "saved": True,
                    "path": str(custom_dir / f"{template_name}.json"),
                }
            )

        return SkillResult.failure(f"Unknown operation: {operation}", component="file_template")


# Update the built-in skills dict
BUILTIN_SKILLS.update(
    {
        "project_build": ProjectBuildSkill,
        "git_extended": GitExtendedSkill,
        "file_template": FileTemplateSkill,
    }
)


# ── MCP Integration Skill ───────────────────────────────────────────


class MCPSkill(Skill[dict[str, Any]]):
    """MCP (Model Context Protocol) integration skill."""

    def _default_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="mcp",
            description="Connect to and invoke MCP (Model Context Protocol) servers",
            version="1.0.0",
            category="integration",
            tags=["mcp", "protocol", "integration", "tools", "resources"],
            timeout_seconds=30,
            parameters_schema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": [
                            "list_servers",
                            "connect_server",
                            "disconnect_server",
                            "list_tools",
                            "call_tool",
                            "list_resources",
                            "read_resource",
                        ],
                        "description": "MCP operation to perform",
                    },
                    "server_id": {
                        "type": "string",
                        "description": "MCP server ID",
                    },
                    "tool_name": {
                        "type": "string",
                        "description": "Name of the tool to call",
                    },
                    "arguments": {
                        "type": "object",
                        "description": "Tool arguments",
                    },
                    "resource_uri": {
                        "type": "string",
                        "description": "Resource URI to read",
                    },
                    "config_path": {
                        "type": "string",
                        "description": "Path to MCP server config file",
                        "default": "mcp_servers.json",
                    },
                },
                "required": ["operation"],
            },
            returns_schema={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "data": {"type": "object"},
                    "error": {"type": "string"},
                },
            },
        )

    def validate_params(self, **kwargs: Any) -> bool:
        op = kwargs.get("operation")
        return op in {
            "list_servers",
            "connect_server",
            "disconnect_server",
            "list_tools",
            "call_tool",
            "list_resources",
            "read_resource",
        }

    async def execute(self, **kwargs: Any) -> SkillResult[dict[str, Any]]:
        operation = kwargs.get("operation")
        server_id = kwargs.get("server_id")
        tool_name = kwargs.get("tool_name")
        arguments = kwargs.get("arguments", {})
        resource_uri = kwargs.get("resource_uri")
        config_path = kwargs.get("config_path", "mcp_servers.json")

        try:
            from app.mcp import create_mcp_manager_from_config
        except ImportError:
            return SkillResult.failure(
                "MCP module not available",
                component="mcp",
            )

        if operation == "list_servers":
            try:
                with open(config_path) as f:
                    config_data = json.load(f)
                servers = [
                    {"server_id": s["server_id"], "name": s["name"], "transport": s["transport"]}
                    for s in config_data.get("servers", [])
                ]
                return SkillResult.success({"servers": servers})
            except FileNotFoundError:
                return SkillResult.success({"servers": []})
            except Exception as e:
                return SkillResult.failure(f"Failed to read config: {e}", component="mcp")

        # For other operations, we need a manager
        try:
            manager = create_mcp_manager_from_config(config_path)
        except Exception as e:
            return SkillResult.failure(f"Failed to create manager: {e}", component="mcp")

        if operation == "connect_server":
            if not server_id:
                return SkillResult.failure("server_id required", component="mcp")
            results = await manager.connect_all()
            connected = results.get(server_id, False)
            return SkillResult.success({"server_id": server_id, "connected": connected})

        if operation == "disconnect_server":
            if not server_id:
                return SkillResult.failure("server_id required", component="mcp")
            client = manager._clients.get(server_id)
            if client:
                await client.disconnect()
                return SkillResult.success({"server_id": server_id, "disconnected": True})
            return SkillResult.failure("Server not found", component="mcp")

        # For operations requiring connection, connect first
        if operation in {"list_tools", "call_tool", "list_resources", "read_resource"}:
            if not server_id:
                return SkillResult.failure("server_id required", component="mcp")
            results = await manager.connect_all()
            if not results.get(server_id, False):
                return SkillResult.failure(
                    f"Failed to connect to server {server_id}", component="mcp"
                )

        if operation == "list_tools":
            tools = manager.list_tools()
            server_tools = [t for t in tools if t.server_id == server_id]
            return SkillResult.success(
                {
                    "server_id": server_id,
                    "tools": [
                        {
                            "name": t.name,
                            "description": t.description,
                            "input_schema": t.input_schema,
                        }
                        for t in server_tools
                    ],
                }
            )

        if operation == "call_tool":
            if not tool_name:
                return SkillResult.failure("tool_name required", component="mcp")
            if not server_id:
                return SkillResult.failure("server_id required", component="mcp")
            try:
                result = await manager.call_tool(server_id, tool_name, arguments)
                return SkillResult.success({"result": result})
            except Exception as e:
                return SkillResult.failure(str(e), component="mcp")

        if operation == "list_resources":
            resources = manager.list_resources()
            server_resources = [r for r in resources if r.server_id == server_id]
            return SkillResult.success(
                {
                    "server_id": server_id,
                    "resources": [
                        {
                            "uri": r.uri,
                            "name": r.name,
                            "description": r.description,
                            "mime_type": r.mime_type,
                        }
                        for r in server_resources
                    ],
                }
            )

        if operation == "read_resource":
            if not resource_uri:
                return SkillResult.failure("resource_uri required", component="mcp")
            if not server_id:
                return SkillResult.failure("server_id required", component="mcp")
            try:
                result = await manager.read_resource(server_id, resource_uri)
                return SkillResult.success({"result": result})
            except Exception as e:
                return SkillResult.failure(str(e), component="mcp")

        return SkillResult.failure(f"Unknown operation: {operation}", component="mcp")
