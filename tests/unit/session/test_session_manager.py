"""Tests for SessionManager lifecycle, messaging, and persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.session import (
    InMemorySessionStore,
    JsonSessionStore,
    SessionManager,
    SessionNotFoundError,
)


def _manager() -> SessionManager:
    return SessionManager(InMemorySessionStore())


class TestLifecycle:
    def test_create_and_get(self) -> None:
        m = _manager()
        s = m.create("learner-1")
        assert s.session_id.startswith("sess-")
        assert m.get(s.session_id).session_id == s.session_id

    def test_get_unknown_raises(self) -> None:
        m = _manager()
        with pytest.raises(SessionNotFoundError):
            m.get("sess-does-not-exist")

    def test_end_marks_terminal(self) -> None:
        m = _manager()
        s = m.create("learner-1")
        ended = m.end(s.session_id)
        assert ended.status.value == "ended"

    def test_resume_reactivates_paused(self) -> None:
        m = _manager()
        s = m.create("learner-1")
        m.end(s.session_id)
        resumed = m.resume(s.session_id)
        assert resumed.status.value == "active"

    def test_list_active(self) -> None:
        m = _manager()
        s1 = m.create("learner-1")
        s2 = m.create("learner-2")
        m.end(s2.session_id)
        ids = {s.session_id for s in m.list_active()}
        assert s1.session_id in ids
        assert s2.session_id not in ids


class TestMessaging:
    def test_record_user_and_assistant(self) -> None:
        m = _manager()
        s = m.create("learner-1")
        m.record_user(s.session_id, "hello")
        m.record_assistant(s.session_id, "hi there")
        conv = m.get(s.session_id).active_conversation()
        assert conv is not None
        assert [msg.role.value for msg in conv.messages] == ["user", "assistant"]

    def test_context_returns_last_n(self) -> None:
        m = _manager()
        s = m.create("learner-1")
        for i in range(10):
            m.record_user(s.session_id, f"msg-{i}")
        ctx = m.context(s.session_id, limit=3)
        assert [msg.content for msg in ctx] == ["msg-7", "msg-8", "msg-9"]


class TestPersistence:
    def test_json_store_round_trip(self, tmp_path: Path) -> None:
        d = tmp_path / "sessions"
        m = SessionManager(JsonSessionStore(d))
        s = m.create("learner-1")
        m.record_user(s.session_id, "remember this")
        m.record_assistant(s.session_id, "ok", grounded=True)

        # A fresh manager reading the same dir reconstructs the session.
        m2 = SessionManager(JsonSessionStore(d))
        s2 = m2.get(s.session_id)
        conv = s2.active_conversation()
        assert conv is not None
        assert [msg.role.value for msg in conv.messages] == ["user", "assistant"]
        assert s2.status.value == "active"

    def test_in_memory_store_load_returns_none_for_unknown(self) -> None:
        assert InMemorySessionStore().load("nope") is None
