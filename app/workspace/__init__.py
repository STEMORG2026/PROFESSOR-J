"""Workspace subsystem — scoped file operations under the safety policy."""

from app.workspace.workspace import (
    WorkspaceError,
    WorkspaceManager,
    WorkspaceSecurityError,
)

__all__ = ["WorkspaceManager", "WorkspaceError", "WorkspaceSecurityError"]
