"""Session subsystem — durable, resumable per-learner conversational sessions.

Sessions hold immutable :class:`~app.domain.session.Session` objects (conversation
history + pedagogical context). The :class:`SessionManager` orchestrates them and
provides pluggable persistence (:class:`SessionStore`). A session id doubles as
the LangGraph checkpoint ``thread_id``, so the cognitive brain and session layer
share the same resume key.
"""

from app.session.session_manager import (
    InMemorySessionStore,
    JsonSessionStore,
    SessionManager,
    SessionNotFoundError,
)

__all__ = [
    "SessionManager",
    "InMemorySessionStore",
    "JsonSessionStore",
    "SessionNotFoundError",
]
