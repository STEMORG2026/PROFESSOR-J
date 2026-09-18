"""Session Manager — fork, resume, export, import sessions.

Modeled on OpenCode sessions and dsh session-query.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SessionData:
    """A session's data."""

    session_id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    parent_id: str | None = None


class SessionManager:
    """Manage sessions — fork, resume, export, import."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionData] = {}

    def create_session(self, title: str = "Untitled", **metadata: Any) -> SessionData:
        """Create a new session."""
        session_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        session = SessionData(
            session_id=session_id,
            title=title,
            created_at=now,
            updated_at=now,
            metadata=metadata,
        )
        self._sessions[session_id] = session
        logger.info("Created session: %s", session_id)
        return session

    def fork_session(self, session_id: str, title: str | None = None) -> SessionData | None:
        """Fork an existing session (copy with new ID, link parent)."""
        source = self._sessions.get(session_id)
        if not source:
            return None
        fork_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        fork = SessionData(
            session_id=fork_id,
            title=title or f"Fork of {source.title}",
            created_at=now,
            updated_at=now,
            messages=list(source.messages),
            metadata=dict(source.metadata),
            parent_id=session_id,
        )
        self._sessions[fork_id] = fork
        logger.info("Forked session %s → %s", session_id, fork_id)
        return fork

    def resume_session(self, session_id: str) -> SessionData | None:
        """Resume an existing session."""
        return self._sessions.get(session_id)

    def export_session(self, session_id: str) -> str | None:
        """Export a session as JSON."""
        session = self._sessions.get(session_id)
        if not session:
            return None
        return json.dumps(session.__dict__, indent=2)

    def import_session(self, data: str) -> SessionData | None:
        """Import a session from JSON."""
        try:
            parsed = json.loads(data)
            session = SessionData(**parsed)
            self._sessions[session.session_id] = session
            return session
        except (json.JSONDecodeError, TypeError):
            return None

    def list_sessions(self) -> list[SessionData]:
        """List all sessions."""
        return list(self._sessions.values())


def create_session_manager() -> SessionManager:
    """Create a session manager."""
    return SessionManager()


__all__ = ["SessionManager", "SessionData", "create_session_manager"]
