"""Built-in Skills — Core skills for PROFESSOR-J Phase 1."""

from __future__ import annotations

import json
import logging
import subprocess  # nosec B404 - used only by the git skill with explicit list args (no shell)
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from app.knowledge.lhs_adapter import LHSKnowledgeAdapter
from app.skills.base import Skill, SkillMetadata, SkillResult
from app.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)

# ── Citation Ledger (for grounded-citations skill) ───────────────────

class CitationLedger:
    """Simple in-memory citation ledger for grounded-citations skill.
    
    Maps URLs to stable numeric IDs. Persists to disk for session continuity.
    """
    
    def __init__(self, ledger_path: Path | None = None):
        self.ledger_path = ledger_path or Path("data/citations/ledger.json")
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self._url_to_id: dict[str, int] = {}
        self._id_to_url: dict[int, str] = {}
        self._id_to_title: dict[int, str] = {}
        self._next_id = 1
        self._load()
    
    def _load(self) -> None:
        if self.ledger_path.exists():
            try:
                data = json.loads(self.ledger_path.read_text())
                self._url_to_id = {k: int(v) for k, v in data.get("url_to_id", {}).items()}
                self._id_to_url = {int(k): v for k, v in data.get("id_to_url", {}).items()}
                self._id_to_title = {int(k): v for k, v in data.get("id_to_title", {}).items()}
                self._next_id = data.get("next_id", len(self._url_to_id) + 1)
            except Exception as e:
                logger.warning("Failed to load citation ledger: %s", e)
    
    def _save(self) -> None:
        try:
            data = {
                "url_to_id": self._url_to_id,
                "id_to_url": {str(k): v for k, v in self._id_to_url.items()},
                "id_to_title": {str(k): v for k, v in self._id_to_title.items()},
                "next_id": self._next_id,
            }
            self.ledger_path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning("Failed to save citation ledger: %s", e)
    
    def add(self, url: str, title: str = "") -> int:
        """Add a URL to the ledger, return its stable ID."""
        normalized = self._normalize_url(url)
        if normalized in self._url_to_id:
            return self._url_to_id[normalized]
        cid = self._next_id
        self._url_to_id[normalized] = cid
        self._id_to_url[cid] = url
        self._id_to_title[cid] = title or url
        self._next_id += 1
        self._save()
        return cid
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL for stable IDs."""
        try:
            parsed = urllib.parse.urlparse(url)
            # Remove fragment, normalize path
            normalized = urllib.parse.urlunparse((
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path.rstrip("/"),
                parsed.params,
                parsed.query,
                ""  # no fragment
            ))
            return normalized
        except Exception:
            return url
    
    def get_id(self, url: str) -> int:
        """Get citation ID for URL, creating if not exists."""
        normalized = self._normalize_url(url)
        if normalized in self._url_to_id:
            return self._url_to_id[normalized]
        # Auto-create if not found (so it always returns an int)
        return self.add(url)
    
    def get_url(self, cid: int) -> str | None:
        return self._id_to_url.get(cid)
    
    def get_title(self, cid: int) -> str | None:
        return self._id_to_title.get(cid)
    
    def render(self, cited_ids: list[int] | None = None) -> str:
        """Render Sources block for cited IDs (or all if None)."""
        ids = cited_ids if cited_ids is not None else sorted(self._id_to_url.keys())
        lines = ["## Sources", ""]
        for cid in ids:
            url = self._id_to_url.get(cid)
            title = self._id_to_title.get(cid)
            if url:
                lines.append(f"[{cid}] {title} — {url}")
        return "\n".join(lines)
    
    def verify(self, draft_text: str) -> tuple[bool, list[str]]:
        """Verify all citations in draft exist in ledger."""
        import re
        cited = re.findall(r'\[(\d+)\]', draft_text)
        errors = []
        for cid_str in cited:
            cid = int(cid_str)
            if cid not in self._id_to_url:
                errors.append(f"Citation [{cid}] not found in ledger")
        return len(errors) == 0, errors

# Global ledger instance
_citation_ledger: CitationLedger | None = None

def get_citation_ledger() -> CitationLedger:
    global _citation_ledger
    if _citation_ledger is None:
        _citation_ledger = CitationLedger()
    return _citation_ledger


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


# ── STEMMA Skill ──────────────────────────────────────────


class LHSTEMSkill(Skill[dict[str, Any]]):
    """Access STEMMA canonical knowledge via consumer adapter."""

    def _default_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="lhstem_knowledge",
            description="Query STEMMA canonical concepts, equations, prerequisites",
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


# Update the built-in skills dict (core skills)
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


# ── Grounded Citations Skill ─────────────────────────────────────────


class GroundedCitationsSkill(Skill[dict[str, Any]]):
    """Ground answers and documents in cited, verifiable sources.

    Every claim from an external source gets an inline numbered citation and a
    Sources block. The ledger maps URLs to stable IDs so citations are verifiable.
    """

    def _default_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="grounded_citations",
            description="Ground answers/documents in cited, verifiable sources with inline citations",
            version="1.0.0",
            category="research",
            tags=["citations", "grounding", "sources", "verification", "research"],
            timeout_seconds=30,
            requires_approval=False,
            parameters_schema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": [
                            "reset",
                            "add_source",
                            "list_sources",
                            "render_sources",
                            "verify_draft",
                            "get_citation_id",
                        ],
                        "description": "Citation ledger operation",
                    },
                    "url": {"type": "string", "description": "Source URL to register"},
                    "title": {"type": "string", "description": "Optional title for the source"},
                    "draft_path": {"type": "string", "description": "Path to draft file to verify"},
                    "draft_text": {"type": "string", "description": "Draft text to verify (alternative to draft_path)"},
                    "cited_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Specific citation IDs to render (default: all)",
                    },
                },
                "required": ["operation"],
            },
            returns_schema={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "citation_id": {"type": "integer"},
                    "sources": {"type": "array", "items": {"type": "object"}},
                    "sources_block": {"type": "string"},
                    "valid": {"type": "boolean"},
                    "errors": {"type": "array", "items": {"type": "string"}},
                    "error": {"type": "string"},
                },
            },
        )

    async def execute(self, **kwargs: Any) -> SkillResult[dict[str, Any]]:
        operation = kwargs["operation"]
        ledger = get_citation_ledger()

        if operation == "reset":
            # Clear the ledger file
            ledger._url_to_id.clear()
            ledger._id_to_url.clear()
            ledger._id_to_title.clear()
            ledger._next_id = 1
            ledger._save()
            return SkillResult.success({"success": True, "message": "Citation ledger reset"})

        if operation == "add_source":
            url = kwargs.get("url", "")
            title = kwargs.get("title", "")
            if not url:
                return SkillResult.failure("url is required", component="grounded_citations")
            cid = ledger.add(url, title)
            return SkillResult.success({"success": True, "citation_id": cid, "url": url})

        if operation == "get_citation_id":
            url = kwargs.get("url", "")
            if not url:
                return SkillResult.failure("url is required", component="grounded_citations")
            cid = ledger.get_id(url)
            if cid is None:
                return SkillResult.failure(f"URL not in ledger: {url}", component="grounded_citations")
            return SkillResult.success({"success": True, "citation_id": cid})

        if operation == "list_sources":
            sources = [
                {"id": cid, "url": ledger.get_url(cid), "title": ledger.get_title(cid)}
                for cid in sorted(ledger._id_to_url.keys())
            ]
            return SkillResult.success({"success": True, "sources": sources})

        if operation == "render_sources":
            cited_ids = kwargs.get("cited_ids")
            block = ledger.render(cited_ids)
            return SkillResult.success({"success": True, "sources_block": block})

        if operation == "verify_draft":
            draft_text = kwargs.get("draft_text")
            draft_path = kwargs.get("draft_path")
            if draft_path and not draft_text:
                try:
                    draft_text = Path(draft_path).read_text(encoding="utf-8")
                except Exception as e:
                    return SkillResult.failure(f"Failed to read draft: {e}", component="grounded_citations")
            if not draft_text:
                return SkillResult.failure("draft_text or draft_path required", component="grounded_citations")
            valid, errors = ledger.verify(draft_text)
            return SkillResult.success({"success": True, "valid": valid, "errors": errors})

        return SkillResult.failure(f"Unknown operation: {operation}", component="grounded_citations")


# ── ArXiv Research Skill ─────────────────────────────────────────────


class ArxivSkill(Skill[dict[str, Any]]):
    """Search and retrieve academic papers from arXiv."""

    def _default_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="arxiv",
            description="Search arXiv papers by keyword, author, category, or ID",
            version="1.0.0",
            category="research",
            tags=["arxiv", "papers", "academic", "science", "search"],
            timeout_seconds=30,
            requires_approval=False,
            parameters_schema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["search", "get_paper", "search_by_author", "search_by_category"],
                        "description": "ArXiv operation",
                    },
                    "query": {"type": "string", "description": "Search query (for search operation)"},
                    "paper_id": {"type": "string", "description": "arXiv paper ID (e.g., 2402.03300)"},
                    "author": {"type": "string", "description": "Author name (for search_by_author)"},
                    "category": {"type": "string", "description": "arXiv category (e.g., cs.AI)"},
                    "max_results": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50},
                    "sort_by": {"type": "string", "enum": ["relevance", "lastUpdatedDate", "submittedDate"], "default": "submittedDate"},
                    "sort_order": {"type": "string", "enum": ["ascending", "descending"], "default": "descending"},
                },
                "required": ["operation"],
            },
            returns_schema={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "papers": {"type": "array", "items": {"type": "object"}},
                    "paper": {"type": "object"},
                    "error": {"type": "string"},
                },
            },
        )

    async def execute(self, **kwargs: Any) -> SkillResult[dict[str, Any]]:
        operation = kwargs["operation"]
        max_results = kwargs.get("max_results", 10)
        sort_by = kwargs.get("sort_by", "submittedDate")
        sort_order = kwargs.get("sort_order", "descending")

        base_url = "https://export.arxiv.org/api/query"
        ns = {"a": "http://www.w3.org/2005/Atom"}

        def parse_entry(entry: ET.Element) -> dict[str, Any]:
            title_elem = entry.find("a:title", ns)
            id_elem = entry.find("a:id", ns)
            published_elem = entry.find("a:published", ns)
            summary_elem = entry.find("a:summary", ns)
            author_elems = entry.findall("a:author", ns)
            category_elems = entry.findall("a:category", ns)

            title = title_elem.text.strip().replace("\n", " ") if title_elem is not None and title_elem.text else ""
            arxiv_id = id_elem.text.strip().split("/abs/")[-1] if id_elem is not None and id_elem.text else ""
            published = published_elem.text[:10] if published_elem is not None and published_elem.text else ""
            author_names = []
            for a in author_elems:
                name_elem = a.find("a:name", ns)
                if name_elem is not None and name_elem.text:
                    author_names.append(name_elem.text)
            authors = ", ".join(author_names)
            summary = summary_elem.text.strip() if summary_elem is not None and summary_elem.text else ""
            cat_terms = [c.get("term") for c in category_elems if c.get("term") is not None]
            cats = ", ".join(cat_terms)  # type: ignore[arg-type]
            return {
                "id": arxiv_id,
                "title": title,
                "authors": authors,
                "published": published,
                "summary": summary,
                "categories": cats,
                "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else "",
                "abs_url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "",
            }

        try:
            if operation == "search":
                query = kwargs.get("query", "")
                if not query:
                    return SkillResult.failure("query is required for search", component="arxiv")
                search_query = f"all:{urllib.parse.quote(query)}"
                url = f"{base_url}?search_query={search_query}&max_results={max_results}&sortBy={sort_by}&sortOrder={sort_order}"

            elif operation == "get_paper":
                paper_id = kwargs.get("paper_id", "")
                if not paper_id:
                    return SkillResult.failure("paper_id is required", component="arxiv")
                url = f"{base_url}?id_list={paper_id}"

            elif operation == "search_by_author":
                author = kwargs.get("author", "")
                if not author:
                    return SkillResult.failure("author is required", component="arxiv")
                search_query = f"au:{urllib.parse.quote(author)}"
                url = f"{base_url}?search_query={search_query}&max_results={max_results}&sortBy={sort_by}&sortOrder={sort_order}"

            elif operation == "search_by_category":
                category = kwargs.get("category", "")
                if not category:
                    return SkillResult.failure("category is required", component="arxiv")
                search_query = f"cat:{urllib.parse.quote(category)}"
                url = f"{base_url}?search_query={search_query}&max_results={max_results}&sortBy={sort_by}&sortOrder={sort_order}"

            else:
                return SkillResult.failure(f"Unknown operation: {operation}", component="arxiv")

            # Fetch and parse
            req = urllib.request.Request(url, headers={"User-Agent": "PROFESSOR-J/1.0"})
            with urllib.request.urlopen(req, timeout=30) as response:
                xml_data = response.read()

            root = ET.fromstring(xml_data)
            entries = root.findall("a:entry", ns)

            if operation == "get_paper" and entries:
                paper = parse_entry(entries[0])
                return SkillResult.success({"success": True, "paper": paper})

            papers = [parse_entry(e) for e in entries]
            return SkillResult.success({"success": True, "papers": papers})

        except Exception as e:
            logger.exception("ArXiv skill failed: %s", e)
            return SkillResult.failure(f"ArXiv request failed: {e}", component="arxiv")


# ── Workspace Synthesis Skill ────────────────────────────────────────


class WorkspaceSynthesisSkill(Skill[dict[str, Any]]):
    """Summarize multi-repo workspaces: read governance, check git, synthesize status."""

    def _default_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="workspace_synthesis",
            description="Summarize multi-repo workspaces — governance, architecture, project status, progress",
            version="1.0.0",
            category="workspace",
            tags=["workspace", "synthesis", "documentation", "governance", "git"],
            timeout_seconds=60,
            requires_approval=False,
            parameters_schema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["summarize_workspace", "summarize_repo", "check_git_status"],
                        "description": "Workspace synthesis operation",
                    },
                    "workspace_root": {"type": "string", "default": "/home/sajan/Projects", "description": "Workspace root path"},
                    "repo_name": {"type": "string", "description": "Specific repository to summarize"},
                    "output_path": {"type": "string", "description": "Optional path to write summary"},
                },
                "required": ["operation"],
            },
            returns_schema={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "summary": {"type": "string"},
                    "repos": {"type": "array", "items": {"type": "object"}},
                    "error": {"type": "string"},
                },
            },
        )

    async def execute(self, **kwargs: Any) -> SkillResult[dict[str, Any]]:
        import subprocess

        operation = kwargs["operation"]
        workspace_root = Path(kwargs.get("workspace_root", "/home/sajan/Projects"))
        repo_name = kwargs.get("repo_name")
        output_path = kwargs.get("output_path")

        def run_cmd(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
            try:
                result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30)
                return result.returncode, result.stdout, result.stderr
            except subprocess.TimeoutExpired:
                return -1, "", "Command timed out"
            except Exception as e:
                return -1, "", str(e)

        def read_file_safe(path: Path) -> str:
            try:
                return path.read_text(encoding="utf-8")[:5000]
            except Exception:
                return ""

        if operation == "check_git_status":
            if not repo_name:
                return SkillResult.failure("repo_name required for check_git_status", component="workspace_synthesis")
            repo_path = workspace_root / repo_name
            if not repo_path.exists():
                return SkillResult.failure(f"Repo not found: {repo_path}", component="workspace_synthesis")
            code, stdout, stderr = run_cmd(["git", "status", "--porcelain"], repo_path)
            code2, stdout2, stderr2 = run_cmd(["git", "log", "--oneline", "-10"], repo_path)
            return SkillResult.success({
                "success": True,
                "repo": repo_name,
                "status": stdout,
                "recent_commits": stdout2,
            })

        if operation == "summarize_repo":
            if not repo_name:
                return SkillResult.failure("repo_name required for summarize_repo", component="workspace_synthesis")
            repo_path = workspace_root / repo_name
            if not repo_path.exists():
                return SkillResult.failure(f"Repo not found: {repo_path}", component="workspace_synthesis")

            # Read key files
            agents_md = read_file_safe(repo_path / "AGENTS.md")
            readme = read_file_safe(repo_path / "README.md")
            roadmap = read_file_safe(repo_path / "docs" / "ROADMAP.md")
            architecture = read_file_safe(repo_path / "ARCHITECTURE.md") or read_file_safe(repo_path / "docs" / "ARCHITECTURE.md")

            # Git status
            code, git_status, _ = run_cmd(["git", "status", "--porcelain"], repo_path)
            code2, git_log, _ = run_cmd(["git", "log", "--oneline", "-5"], repo_path)

            summary = f"""# {repo_name} Summary

## Git Status
```
{git_status or "(clean)"}
```

## Recent Commits
```
{git_log or "(none)"}
```

## Key Documents
### AGENTS.md (excerpt)
```
{agents_md[:2000] if agents_md else "(not found)"}
```

### README.md (excerpt)
```
{readme[:2000] if readme else "(not found)"}
```

### ROADMAP.md (excerpt)
```
{roadmap[:2000] if roadmap else "(not found)"}
```

### ARCHITECTURE.md (excerpt)
```
{architecture[:2000] if architecture else "(not found)"}
```
"""

            if output_path:
                Path(output_path).write_text(summary, encoding="utf-8")

            return SkillResult.success({"success": True, "summary": summary, "repo": repo_name})

        if operation == "summarize_workspace":
            # Discover all repos
            repos = []
            for item in workspace_root.iterdir():
                if item.is_dir() and (item / ".git").exists():
                    repos.append(item.name)

            all_summaries: list[dict[str, Any]] = []
            for repo in repos:
                repo_path = workspace_root / repo
                code, git_status, _ = run_cmd(["git", "status", "--porcelain"], repo_path)
                code2, git_log, _ = run_cmd(["git", "log", "--oneline", "-3"], repo_path)
                agents_md = read_file_safe(repo_path / "AGENTS.md")

                all_summaries.append({
                    "name": repo,
                    "git_clean": not git_status.strip(),
                    "recent_commits": git_log.strip(),
                    "has_agents_md": bool(agents_md),
                })

            summary = f"""# Workspace Synthesis — {workspace_root}

## Repositories ({len(repos)} total)
"""

            for r in all_summaries:
                status = "✅ clean" if r["git_clean"] else "⚠️ dirty"
                summary += f"\n### {r['name']} {status}\n"
                recent_commits = r["recent_commits"]
                if recent_commits:
                    summary += f"Recent: {recent_commits.split(chr(10))[0]}\n"
                summary += f"AGENTS.md: {'yes' if r['has_agents_md'] else 'no'}\n"

            if output_path:
                Path(output_path).write_text(summary, encoding="utf-8")

            return SkillResult.success({"success": True, "summary": summary, "repos": all_summaries})

        return SkillResult.failure(f"Unknown operation: {operation}", component="workspace_synthesis")


# ── GitHub Skills ────────────────────────────────────────────────────


class GitHubAuthSkill(Skill[dict[str, Any]]):
    """GitHub authentication setup for PROFESSOR-J."""

    def _default_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="github_auth",
            description="Set up GitHub authentication (HTTPS tokens, SSH keys, gh CLI login)",
            version="1.0.0",
            category="github",
            tags=["github", "auth", "cli", "setup"],
            timeout_seconds=30,
            requires_approval=False,
            parameters_schema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["check_status", "setup_gh_cli", "setup_https_token", "setup_ssh_key"],
                        "description": "Auth operation",
                    },
                    "token": {"type": "string", "description": "GitHub personal access token"},
                    "ssh_key_path": {"type": "string", "description": "Path to SSH private key"},
                },
                "required": ["operation"],
            },
            returns_schema={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "authenticated": {"type": "boolean"},
                    "method": {"type": "string"},
                    "user": {"type": "string"},
                    "error": {"type": "string"},
                },
            },
        )

    async def execute(self, **kwargs: Any) -> SkillResult[dict[str, Any]]:
        import subprocess
        import os

        operation = kwargs["operation"]

        def run_cmd(cmd: list[str], input_data: str | None = None) -> tuple[int, str, str]:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, input=input_data)
                return result.returncode, result.stdout, result.stderr
            except Exception as e:
                return -1, "", str(e)

        if operation == "check_status":
            # Check gh CLI
            code, stdout, _ = run_cmd(["gh", "auth", "status"])
            if code == 0:
                return SkillResult.success({"success": True, "authenticated": True, "method": "gh_cli", "user": stdout.strip()})
            # Check git credential helper
            code, stdout, _ = run_cmd(["git", "credential", "fill"])
            return SkillResult.success({"success": True, "authenticated": code == 0, "method": "git_credential" if code == 0 else "none"})

        if operation == "setup_gh_cli":
            token = kwargs.get("token")
            if not token:
                return SkillResult.failure("token required for gh CLI setup", component="github_auth")
            code, _, stderr = run_cmd(["gh", "auth", "login", "--with-token"], input_data=token)
            if code == 0:
                return SkillResult.success({"success": True, "message": "gh CLI authenticated"})
            return SkillResult.failure(f"gh auth failed: {stderr}", component="github_auth")

        if operation == "setup_https_token":
            token = kwargs.get("token")
            if not token:
                return SkillResult.failure("token required", component="github_auth")
            # Configure git to use token
            run_cmd(["git", "config", "--global", "credential.helper", "store"])
            # Note: actual credential storage requires user interaction or git-credential-store
            return SkillResult.success({"success": True, "message": "Configured git credential helper; use token on next push"})

        if operation == "setup_ssh_key":
            ssh_key_path = kwargs.get("ssh_key_path", os.path.expanduser("~/.ssh/id_ed25519"))
            if not os.path.exists(ssh_key_path):
                return SkillResult.failure(f"SSH key not found: {ssh_key_path}", component="github_auth")
            # Add to ssh-agent
            run_cmd(["ssh-add", ssh_key_path])
            return SkillResult.success({"success": True, "message": f"Added SSH key: {ssh_key_path}"})

        return SkillResult.failure(f"Unknown operation: {operation}", component="github_auth")


class GitHubCodeReviewSkill(Skill[dict[str, Any]]):
    """Review PRs: diffs, inline comments via gh or REST."""

    def _default_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="github_code_review",
            description="Review PRs: diffs, inline comments via gh or REST",
            version="1.0.0",
            category="github",
            tags=["github", "code-review", "pr", "quality"],
            timeout_seconds=60,
            requires_approval=False,
            parameters_schema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["review_local", "review_pr", "view_pr", "get_diff", "submit_review"],
                        "description": "Review operation",
                    },
                    "pr_number": {"type": "integer", "description": "PR number to review"},
                    "repo": {"type": "string", "description": "Repository (owner/repo)"},
                    "base_branch": {"type": "string", "default": "main", "description": "Base branch for local review"},
                    "review_body": {"type": "string", "description": "Review summary body"},
                    "event": {"type": "string", "enum": ["APPROVE", "REQUEST_CHANGES", "COMMENT"], "default": "COMMENT"},
                    "comments": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string"},
                                "line": {"type": "integer"},
                                "body": {"type": "string"},
                                "side": {"type": "string", "enum": ["LEFT", "RIGHT"], "default": "RIGHT"},
                            },
                            "required": ["path", "line", "body"],
                        },
                        "description": "Inline comments",
                    },
                },
                "required": ["operation"],
            },
            returns_schema={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "diff": {"type": "string"},
                    "pr_info": {"type": "object"},
                    "review_submitted": {"type": "boolean"},
                    "error": {"type": "string"},
                },
            },
        )

    async def execute(self, **kwargs: Any) -> SkillResult[dict[str, Any]]:
        import subprocess
        import os

        operation = kwargs["operation"]
        pr_number = kwargs.get("pr_number")
        repo = kwargs.get("repo")
        base_branch = kwargs.get("base_branch", "main")

        def run_cmd(cmd: list[str], input_data: str | None = None) -> tuple[int, str, str]:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, input=input_data)
                return result.returncode, result.stdout, result.stderr
            except Exception as e:
                return -1, "", str(e)

        # Auto-detect repo from git remote if not provided
        if not repo:
            code, stdout, _ = run_cmd(["git", "remote", "get-url", "origin"])
            if code == 0:
                remote = stdout.strip()
                if "github.com" in remote:
                    repo = remote.split("github.com")[-1].strip(":/. ").replace(".git", "")

        if operation == "review_local":
            # Review local changes vs base branch
            code, stdout, _ = run_cmd(["git", "diff", f"{base_branch}...HEAD", "--stat"])
            code2, diff, _ = run_cmd(["git", "diff", f"{base_branch}...HEAD"])
            return SkillResult.success({"success": True, "stat": stdout, "diff": diff[:10000]})

        if operation == "view_pr":
            if not pr_number or not repo:
                return SkillResult.failure("pr_number and repo required", component="github_code_review")
            code, stdout, _ = run_cmd(["gh", "pr", "view", str(pr_number), "--repo", repo, "--json", "title,author,baseRefName,headRefName,state,body"])
            return SkillResult.success({"success": True, "pr_info": json.loads(stdout) if code == 0 else {}, "error": "" if code == 0 else "Failed to view PR"})

        if operation == "get_diff":
            if not pr_number or not repo:
                return SkillResult.failure("pr_number and repo required", component="github_code_review")
            code, stdout, _ = run_cmd(["gh", "pr", "diff", str(pr_number), "--repo", repo])
            return SkillResult.success({"success": True, "diff": stdout[:10000]})

        if operation == "submit_review":
            if not pr_number or not repo:
                return SkillResult.failure("pr_number and repo required", component="github_code_review")
            event = kwargs.get("event", "COMMENT")
            body = kwargs.get("review_body", "Reviewed by PROFESSOR-J")
            comments = kwargs.get("comments", [])

            if comments:
                # Build inline comments JSON
                comments_json = json.dumps(comments)
                code, stdout, stderr = run_cmd([
                    "gh", "api", f"repos/{repo}/pulls/{pr_number}/reviews",
                    "--method", "POST",
                    "-f", f"event={event}",
                    "-f", f"body={body}",
                    "-f", f"comments={comments_json}",
                ])
            else:
                code, stdout, stderr = run_cmd([
                    "gh", "pr", "review", str(pr_number), "--repo", repo,
                    f"--{event.lower()}", "-b", body,
                ])

            if code == 0:
                return SkillResult.success({"success": True, "review_submitted": True})
            return SkillResult.failure(f"Review failed: {stderr}", component="github_code_review")

        return SkillResult.failure(f"Unknown operation: {operation}", component="github_code_review")


class GitHubPRWorkflowSkill(Skill[dict[str, Any]]):
    """GitHub PR lifecycle: branch, commit, open, CI, merge."""

    def _default_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="github_pr_workflow",
            description="GitHub PR lifecycle: branch, commit, open, CI, merge",
            version="1.0.0",
            category="github",
            tags=["github", "pr", "ci", "merge", "workflow"],
            timeout_seconds=120,
            requires_approval=False,
            parameters_schema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["create_branch", "commit", "push", "create_pr", "check_ci", "merge_pr", "auto_merge"],
                        "description": "PR workflow operation",
                    },
                    "branch_name": {"type": "string", "description": "Branch name"},
                    "base_branch": {"type": "string", "default": "main", "description": "Base branch"},
                    "commit_message": {"type": "string", "description": "Commit message"},
                    "pr_title": {"type": "string", "description": "PR title"},
                    "pr_body": {"type": "string", "description": "PR body"},
                    "repo": {"type": "string", "description": "Repository (owner/repo)"},
                    "pr_number": {"type": "integer", "description": "PR number"},
                    "merge_method": {"type": "string", "enum": ["squash", "merge", "rebase"], "default": "squash"},
                },
                "required": ["operation"],
            },
            returns_schema={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "branch": {"type": "string"},
                    "pr_number": {"type": "integer"},
                    "pr_url": {"type": "string"},
                    "ci_status": {"type": "string"},
                    "merged": {"type": "boolean"},
                    "error": {"type": "string"},
                },
            },
        )

    async def execute(self, **kwargs: Any) -> SkillResult[dict[str, Any]]:
        import subprocess

        operation = kwargs["operation"]
        branch_name = kwargs.get("branch_name")
        base_branch = kwargs.get("base_branch", "main")
        commit_message = kwargs.get("commit_message")
        pr_title = kwargs.get("pr_title")
        pr_body = kwargs.get("pr_body", "")
        repo = kwargs.get("repo")
        pr_number = kwargs.get("pr_number")
        merge_method = kwargs.get("merge_method", "squash")

        def run_cmd(cmd: list[str]) -> tuple[int, str, str]:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                return result.returncode, result.stdout, result.stderr
            except Exception as e:
                return -1, "", str(e)

        # Auto-detect repo
        if not repo:
            code, stdout, _ = run_cmd(["git", "remote", "get-url", "origin"])
            if code == 0:
                remote = stdout.strip()
                if "github.com" in remote:
                    repo = remote.split("github.com")[-1].strip(":/. ").replace(".git", "")

        if operation == "create_branch":
            if not branch_name:
                return SkillResult.failure("branch_name required", component="github_pr_workflow")
            run_cmd(["git", "fetch", "origin"])
            run_cmd(["git", "checkout", base_branch])
            run_cmd(["git", "pull", "origin", base_branch])
            code, _, stderr = run_cmd(["git", "checkout", "-b", branch_name])
            if code == 0:
                return SkillResult.success({"success": True, "branch": branch_name})
            return SkillResult.failure(f"Branch creation failed: {stderr}", component="github_pr_workflow")

        if operation == "commit":
            if not commit_message:
                return SkillResult.failure("commit_message required", component="github_pr_workflow")
            run_cmd(["git", "add", "-A"])
            code, _, stderr = run_cmd(["git", "commit", "-m", commit_message])
            if code == 0:
                return SkillResult.success({"success": True, "message": "Committed"})
            return SkillResult.failure(f"Commit failed: {stderr}", component="github_pr_workflow")

        if operation == "push":
            code, _, stderr = run_cmd(["git", "push", "-u", "origin", "HEAD"])
            if code == 0:
                return SkillResult.success({"success": True, "message": "Pushed"})
            return SkillResult.failure(f"Push failed: {stderr}", component="github_pr_workflow")

        if operation == "create_pr":
            if not pr_title or not repo:
                return SkillResult.failure("pr_title and repo required", component="github_pr_workflow")
            code, stdout, stderr = run_cmd([
                "gh", "pr", "create", "--repo", repo,
                "--title", pr_title,
                "--body", pr_body,
                "--base", base_branch,
            ])
            if code == 0:
                # Extract PR number from output
                import re
                match = re.search(r"#(\d+)", stdout)
                pr_num = int(match.group(1)) if match else None
                return SkillResult.success({"success": True, "pr_number": pr_num, "pr_url": stdout.strip()})
            return SkillResult.failure(f"PR creation failed: {stderr}", component="github_pr_workflow")

        if operation == "check_ci":
            if not pr_number or not repo:
                return SkillResult.failure("pr_number and repo required", component="github_pr_workflow")
            code, stdout, _ = run_cmd(["gh", "pr", "checks", str(pr_number), "--repo", repo, "--json", "name,state,conclusion"])
            return SkillResult.success({"success": True, "ci_status": stdout if code == 0 else "failed"})

        if operation == "merge_pr":
            if not pr_number or not repo:
                return SkillResult.failure("pr_number and repo required", component="github_pr_workflow")
            code, _, stderr = run_cmd([
                "gh", "pr", "merge", str(pr_number), "--repo", repo,
                "--" + merge_method, "--delete-branch",
            ])
            if code == 0:
                return SkillResult.success({"success": True, "merged": True})
            return SkillResult.failure(f"Merge failed: {stderr}", component="github_pr_workflow")

        if operation == "auto_merge":
            if not pr_number or not repo:
                return SkillResult.failure("pr_number and repo required", component="github_pr_workflow")
            code, _, stderr = run_cmd([
                "gh", "pr", "merge", str(pr_number), "--repo", repo,
                "--auto", "--" + merge_method, "--delete-branch",
            ])
            if code == 0:
                return SkillResult.success({"success": True, "merged": True, "auto_merge_enabled": True})
            return SkillResult.failure(f"Auto-merge failed: {stderr}", component="github_pr_workflow")

        return SkillResult.failure(f"Unknown operation: {operation}", component="github_pr_workflow")


# Update the built-in skills dict (ecosystem development agent skills)
BUILTIN_SKILLS.update(
    {
        "grounded_citations": GroundedCitationsSkill,
        "arxiv": ArxivSkill,
        "workspace_synthesis": WorkspaceSynthesisSkill,
        "github_auth": GitHubAuthSkill,
        "github_code_review": GitHubCodeReviewSkill,
        "github_pr_workflow": GitHubPRWorkflowSkill,
    }
)
