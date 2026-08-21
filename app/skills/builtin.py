"""Built-in Skills — Core skills for PROFESSOR-J Phase 1."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from app.skills.base import Skill, SkillMetadata, SkillResult
from app.exceptions import SandboxError, ToolNotFoundError

logger = logging.getLogger(__name__)


# ── Filesystem Skill ────────────────────────────────────────────────

class FilesystemSkill(Skill):
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
                    "content": {"type": "string", "description": "Content to write (for write operation)"},
                    "recursive": {"type": "boolean", "default": False, "description": "Recursive operation"},
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

class GitSkill(Skill):
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
                        "enum": ["status", "diff", "log", "commit", "branch", "push", "pull", "add"],
                        "description": "Git operation to perform",
                    },
                    "args": {"type": "array", "items": {"type": "string"}, "default": []},
                    "cwd": {"type": "string", "description": "Working directory"},
                    "message": {"type": "string", "description": "Commit message (for commit)"},
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
        return op in {"status", "diff", "log", "commit", "branch", "push", "pull", "add"}

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

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=cwd)

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

class WebSearchSkill(Skill):
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
                    "max_results": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50},
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
        # This would use MCP to call the brave-search server
        # For now, return a placeholder - actual implementation uses MCP client
        query = kwargs.get("query", "")
        max_results = kwargs.get("max_results", 10)

        return SkillResult.success({
            "success": True,
            "results": [],
            "note": f"Web search for '{query}' (max {max_results} results) - MCP implementation pending",
        })


# ── Code Execution Skill ──────────────────────────────────────────

class CodeExecutionSkill(Skill):
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
                    "timeout": {"type": "integer", "default": 10, "minimum": 1, "maximum": 60},
                    "memory_mb": {"type": "integer", "default": 512, "minimum": 64, "maximum": 2048},
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
        code = kwargs["code"]
        timeout = kwargs.get("timeout", 10)
        memory_mb = kwargs.get("memory_mb", 512)

        try:
            # This would use the internal sandbox (app/tools/sandbox.py)
            # For now, return a placeholder
            return SkillResult.success({
                "success": True,
                "stdout": "",
                "stderr": "",
                "return_code": 0,
                "execution_time_ms": 0,
                "note": f"Code execution (timeout={timeout}s, mem={memory_mb}MB) - sandbox implementation pending",
            })
        except SandboxError as e:
            return SkillResult.failure(str(e))
        except Exception as e:
            logger.exception("Code execution failed: %s", e)
            return SkillResult.failure(str(e))


# ── LearningHubSTEM Skill ──────────────────────────────────────────

class LHSTEMSkill(Skill):
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
                        "enum": ["get_concept", "get_prerequisites", "search", "has_concept"],
                        "description": "Operation to perform",
                    },
                    "entity_id": {"type": "string", "description": "LHSTEM entity ID (e.g. lhs:phys.force)"},
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

    async def execute(self, **kwargs: Any) -> SkillResult[dict[str, Any]]:
        operation = kwargs["operation"]
        entity_id = kwargs.get("entity_id", "")
        query = kwargs.get("query", "")

        # This would use the LHSKnowledgeAdapter
        # For now, return placeholder
        return SkillResult.success({
            "success": True,
            "note": f"LHSTEM {operation} for {entity_id or query} - adapter implementation pending",
        })


# ── Memory Skill ───────────────────────────────────────────────────

class MemorySkill(Skill):
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
                    "memory_id": {"type": "string", "description": "Memory ID for update/delete"},
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
        operation = kwargs["operation"]

        # This would use the MemoryService
        return SkillResult.success({
            "success": True,
            "note": f"Memory {operation} - MemoryService implementation pending",
        })


# ── Skill Factory ──────────────────────────────────────────────────

BUILTIN_SKILLS: dict[str, type[Skill]] = {
    "filesystem": FilesystemSkill,
    "git": GitSkill,
    "web_search": WebSearchSkill,
    "code_execution": CodeExecutionSkill,
    "lhstem_knowledge": LHSTEMSkill,
    "memory": MemorySkill,
}


def create_builtin_skills() -> dict[str, Skill]:
    """Create instances of all built-in skills."""
    return {name: cls() for name, cls in BUILTIN_SKILLS.items()}


def register_builtin_skills(registry) -> int:
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
