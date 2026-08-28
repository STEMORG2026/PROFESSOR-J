"""WorkspaceManager — scoped, bounded file operations for a learner's workspace.

Every operation is rooted inside a dedicated base directory so an agent cannot
read or write outside the learner's workspace. Path-escape prevention and size
bounds are enforced here as the first line of defense.

Safety tiers are enforced by the :class:`~app.tools.executor.ToolExecutor`: an
agent never calls the workspace directly — it dispatches through the executor,
which decides SAFE vs DESTRUCTIVE and applies human approval (HITL) for
DESTRUCTIVE operations. The workspace itself stays plain and deterministic.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.exceptions import ProfessorError

logger = logging.getLogger(__name__)


class WorkspaceError(ProfessorError):
    """Base workspace failure."""

    code = "WORKSPACE_ERROR"


class WorkspaceSecurityError(WorkspaceError):
    """Raised when an operation would escape the workspace root."""

    code = "WORKSPACE_SECURITY"


class WorkspaceManager:
    """Path-scoped file operations under the safety policy."""

    def __init__(self, root: str | Path, max_bytes: int = 1_000_000) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes

    # ── Path safety ──

    def _resolve(self, relative: str) -> Path:
        """Resolve a relative path and ensure it stays inside the root."""
        target = (self.root / relative).resolve()
        if not target.is_relative_to(self.root):
            raise WorkspaceSecurityError(f"Path escapes workspace root: {relative!r}")
        return target

    # ── Read-only operations ──

    def exists(self, relative: str) -> bool:
        """Check whether a workspace file/dir exists."""
        return self._resolve(relative).exists()

    def read(self, relative: str) -> dict[str, Any]:
        """Read a text file from the workspace (bounded size)."""
        path = self._resolve(relative)
        if not path.is_file():
            return {"success": False, "error": f"Not a file: {relative}"}
        size = path.stat().st_size
        if size > self.max_bytes:
            return {
                "success": False,
                "error": f"File too large ({size} > {self.max_bytes} bytes)",
            }
        return {"success": True, "content": path.read_text(encoding="utf-8")}

    def list(self, relative: str = ".") -> dict[str, Any]:
        """List entries under a workspace directory (non-recursive)."""
        path = self._resolve(relative)
        if not path.is_dir():
            return {"success": False, "error": f"Not a directory: {relative}"}
        entries = []
        for child in sorted(path.iterdir()):
            entries.append(
                {
                    "name": child.name,
                    "type": "dir" if child.is_dir() else "file",
                    "size": child.stat().st_size if child.is_file() else 0,
                }
            )
        return {"success": True, "entries": entries}

    # ── Mutating operations ──

    def write(self, relative: str, content: str) -> dict[str, Any]:
        """Write a file into the workspace (creating parents)."""
        path = self._resolve(relative)
        if len(content.encode("utf-8")) > self.max_bytes:
            return {
                "success": False,
                "error": f"Content exceeds {self.max_bytes} bytes",
            }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {"success": True, "path": str(path)}

    def delete(self, relative: str) -> dict[str, Any]:
        """Delete a file or directory inside the workspace."""
        path = self._resolve(relative)
        if path == self.root or not path.exists():
            return {"success": False, "error": f"Nothing to delete: {relative}"}
        if path.is_dir():
            import shutil

            shutil.rmtree(path)
        else:
            path.unlink()
        return {"success": True}


__all__ = [
    "WorkspaceManager",
    "WorkspaceError",
    "WorkspaceSecurityError",
]
