"""SessionManager — orchestration of durable, resumable learner sessions.

Sits on the immutable :class:`~app.domain.session.Session` / ``Conversation`` /
``Message`` domain types. The manager owns the registry of live sessions, offers
CRUD + append operations, and persists sessions through a pluggable
:class:`SessionStore` so they survive process restarts.

Every session id is a valid LangGraph checkpoint ``thread_id``, so a caller can
resume the cognitive/tutoring brain for the same learner by passing the session
id through to the graph config. The store interface (in-memory or JSON file here)
is the seam to a durable SQL key-value store in Phase 9.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.domain.session import (
    Message,
    MessageRole,
    Provenance,
    Session,
    SessionStatus,
)
from app.exceptions import ProfessorError

logger = logging.getLogger(__name__)

_SERIALIZABLE = {"MessageRole", "SessionStatus"}


class SessionNotFoundError(ProfessorError):
    """Raised when a requested session does not exist."""

    code = "SESSION_NOT_FOUND"

    def __init__(self, session_id: str) -> None:
        super().__init__(f"No such session: {session_id}")
        self.session_id = session_id


class SessionStore(ABC):
    """Persistence contract for sessions (in-memory or durable)."""

    @abstractmethod
    def save(self, session: Session) -> None:
        """Persist a session snapshot."""

    @abstractmethod
    def load(self, session_id: str) -> Session | None:
        """Load a session snapshot, or None if absent."""

    @abstractmethod
    def list_ids(self) -> list[str]:
        """List known session ids."""

    @abstractmethod
    def delete(self, session_id: str) -> None:
        """Remove a session snapshot."""


class InMemorySessionStore(SessionStore):
    """Volatile session store (dev/tests)."""

    def __init__(self) -> None:
        self._data: dict[str, Session] = {}

    def save(self, session: Session) -> None:
        self._data[session.session_id] = session

    def load(self, session_id: str) -> Session | None:
        return self._data.get(session_id)

    def list_ids(self) -> list[str]:
        return list(self._data.keys())

    def delete(self, session_id: str) -> None:
        self._data.pop(session_id, None)


def _encode(obj: Any) -> Any:
    """Recursively encode a dataclass/enum/datetime tree into JSON-safe values."""
    if isinstance(obj, MessageRole | SessionStatus):
        return obj.value
    if hasattr(obj, "isoformat"):  # datetime
        return obj.isoformat()
    if hasattr(obj, "__dataclass_fields__"):  # dataclass
        return {k: _encode(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): _encode(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_encode(v) for v in obj]
    return obj


def _session_to_dict(session: Session) -> dict[str, Any]:
    """Encode a Session (enums -> values, dates -> iso) for JSON persistence."""
    encoded = _encode(session)
    assert isinstance(encoded, dict)  # pragmatic: Session is a dataclass
    return encoded


def _session_from_dict(data: dict[str, Any]) -> Session:
    """Rebuild a Session from its JSON dict (best-effort reconstruction)."""
    # Round-trip through the domain models via asdict is lossy for enums/dates,
    # so we rebuild the top-level + conversations manually.
    from app.domain.session import Conversation  # local import avoids cycles

    conversations: list[Conversation] = []
    for conv in data.get("conversations", []):
        msgs = []
        for m in conv.get("messages", []):
            prov_raw = m.get("provenance")
            provenance = (
                Provenance(
                    source=prov_raw["source"],
                    grounded=bool(prov_raw.get("grounded", False)),
                    entity_ids=tuple(prov_raw.get("entity_ids", ())),
                    review_status=prov_raw.get("review_status"),
                    metadata=dict(prov_raw.get("metadata", {})),
                )
                if prov_raw
                else None
            )
            msgs.append(
                Message(
                    role=MessageRole(m["role"]),
                    content=m["content"],
                    message_id=m["message_id"],
                    provenance=provenance,
                    tool_calls=tuple(m.get("tool_calls", ())),
                    tool_results=tuple(m.get("tool_results", ())),
                    metadata=dict(m.get("metadata", {})),
                )
            )
        conversations.append(
            Conversation(
                session_id=conv["session_id"],
                conversation_id=conv["conversation_id"],
                messages=tuple(msgs),
                active_concept=conv.get("active_concept"),
                tutoring_mode=conv.get("tutoring_mode", "socratic_mentor"),
                metadata=dict(conv.get("metadata", {})),
            )
        )
    return Session(
        learner_id=data["learner_id"],
        session_id=data["session_id"],
        status=SessionStatus(data.get("status", "active")),
        conversations=tuple(conversations),
        active_conversation_id=data.get("active_conversation_id"),
        context_window=int(data.get("context_window", 20)),
        metadata=dict(data.get("metadata", {})),
    )


class JsonSessionStore(SessionStore):
    """Session store persisted to a JSON file (one file per session, or aggregate).

    Uses a per-session file under ``directory`` named ``<session_id>.json``.
    """

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        return self.directory / f"{session_id}.json"

    def save(self, session: Session) -> None:
        self._path(session.session_id).write_text(
            json.dumps(_session_to_dict(session)), encoding="utf-8"
        )

    def load(self, session_id: str) -> Session | None:
        path = self._path(session_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Corrupt session file: %s", path)
            return None
        return _session_from_dict(data)

    def list_ids(self) -> list[str]:
        return sorted(p.stem for p in self.directory.glob("*.json"))

    def delete(self, session_id: str) -> None:
        self._path(session_id).unlink(missing_ok=True)


class SessionManager:
    """High-level orchestrator for the lifecycle of learner sessions."""

    def __init__(self, store: SessionStore | None = None) -> None:
        self.store = store or InMemorySessionStore()
        self._live: dict[str, Session] = {}

    # ── Lifecycle ──

    def create(self, learner_id: str) -> Session:
        """Create a new active session for a learner and persist it."""
        session = Session(learner_id=learner_id)
        self._live[session.session_id] = session
        self.store.save(session)
        logger.info("created session %s for learner %s", session.session_id, learner_id)
        return session

    def get(self, session_id: str) -> Session:
        """Fetch a session, loading from store if not live."""
        session = self._live.get(session_id) or self.store.load(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session

    def resume(self, session_id: str) -> Session:
        """Resume a session, activating it if it was paused/ended."""
        session = self.get(session_id)
        if session.status in (SessionStatus.PAUSED, SessionStatus.ENDED):
            session = session.with_status(SessionStatus.ACTIVE)
            self._persist(session)
        return session

    def end(self, session_id: str) -> Session:
        """End a session (terminal status)."""
        session = self.get(session_id).with_status(SessionStatus.ENDED)
        self._persist(session)
        return session

    def archive(self, session_id: str) -> Session:
        """Archive a session (retained but inactive)."""
        session = self.get(session_id).with_status(SessionStatus.ARCHIVED)
        self._persist(session)
        return session

    def delete(self, session_id: str) -> None:
        """Permanently delete a session."""
        self._live.pop(session_id, None)
        self.store.delete(session_id)

    def list_active(self) -> list[Session]:
        """List currently active sessions."""
        return [s for s in self._live.values() if s.status == SessionStatus.ACTIVE]

    # ── Message intake ──

    def record_user(
        self,
        session_id: str,
        text: str,
        *,
        provenance: Provenance | None = None,
    ) -> Session:
        """Append a user message to the session's active conversation."""
        return self._append(
            session_id, Message(role=MessageRole.USER, content=text, provenance=provenance)
        )

    def record_assistant(
        self,
        session_id: str,
        text: str,
        *,
        provenance: Provenance | None = None,
        grounded: bool = False,
    ) -> Session:
        """Append an assistant message to the session's active conversation."""
        if provenance is None and grounded:
            provenance = Provenance(source="brain", grounded=True)
        return self._append(
            session_id,
            Message(role=MessageRole.ASSISTANT, content=text, provenance=provenance),
        )

    def _append(self, session_id: str, message: Message) -> Session:
        session = self.get(session_id)
        updated = session.add_message(message)
        self._persist(updated)
        return updated

    # ── Context window ──

    def context(self, session_id: str, limit: int = 16) -> list[Message]:
        """Return the last ``limit`` messages from the active conversation."""
        session = self.get(session_id)
        conv = session.active_conversation()
        if conv is None:
            return []
        return list(conv.messages[-limit:])

    # ── Internals ──

    def _persist(self, session: Session) -> None:
        self._live[session.session_id] = session
        self.store.save(session)


__all__ = [
    "SessionManager",
    "SessionStore",
    "InMemorySessionStore",
    "JsonSessionStore",
    "SessionNotFoundError",
]
