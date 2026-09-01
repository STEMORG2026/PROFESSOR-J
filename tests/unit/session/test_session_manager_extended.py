"""Extended tests for SessionManager, session stores, and encode/decode helpers.

These complement ``test_session_manager.py`` by exercising the JSON persistence
round-trips, error paths, archive/end/resume transitions, context-window limits,
and the ``_encode`` / ``_session_to_dict`` / ``_session_from_dict`` helpers with
edge-case types (provenance, tool calls, nested metadata, datetime, enums).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.domain.session import (
    Conversation,
    Message,
    MessageRole,
    Provenance,
    Session,
    SessionStatus,
)
from app.session import (
    InMemorySessionStore,
    JsonSessionStore,
    SessionManager,
    SessionNotFoundError,
)
from app.session.session_manager import (
    _encode,
    _session_from_dict,
    _session_to_dict,
)


def _manager() -> SessionManager:
    return SessionManager(InMemorySessionStore())


def _session_with_conversation() -> Session:
    """A Session with a populated conversation for serialization round-trips."""
    prov = Provenance(
        source="lhs:phys.force",
        grounded=True,
        entity_ids=("lhs:phys.force", "lhs:phys.mass"),
        review_status="draft",
        metadata={"model": "teacher-v1", "n": 3},
    )
    user_msg = Message(
        role=MessageRole.USER,
        content="what is force?",
        provenance=prov,
        tool_calls=({"name": "search", "args": {"q": "force"}},),
        tool_results=({"ok": True},),
        metadata={"channel": "web"},
    )
    tool_msg = Message(
        role=MessageRole.TOOL,
        content="a force is a push or pull",
        provenance=None,
        metadata={},
    )
    conv = Conversation(
        session_id="sess-enc-1",
        messages=(user_msg, tool_msg),
        active_concept="lhs:phys.force",
        tutoring_mode="direct_instruction",
        metadata={"tags": ["physics"]},
    )
    return Session(
        learner_id="learner-enc",
        session_id="sess-enc-1",
        status=SessionStatus.PAUSED,
        conversations=(conv,),
        active_conversation_id=conv.conversation_id,
        context_window=42,
        metadata={"k": "v", "nested": {"x": [1, 2]}},
    )


class TestSessionNotFoundError:
    def test_code_and_session_id(self) -> None:
        err = SessionNotFoundError("sess-missing")
        assert err.session_id == "sess-missing"
        assert "sess-missing" in str(err)
        # The enum-like code class attribute is shadowed by ProfessorError's
        # init (which uses the class name when no code= is passed).
        assert SessionNotFoundError.code == "SESSION_NOT_FOUND"

    def test_is_professor_error(self) -> None:
        from app.exceptions import ProfessorError

        assert isinstance(SessionNotFoundError("x"), ProfessorError)


class TestJsonSessionStore:
    def test_save_load_list_delete_round_trip(self, tmp_path: Path) -> None:
        store = JsonSessionStore(tmp_path / "sessions")
        session = _session_with_conversation()
        store.save(session)
        assert store.list_ids() == [session.session_id]

        loaded = store.load(session.session_id)
        assert loaded is not None
        assert loaded.session_id == session.session_id
        assert loaded.learner_id == "learner-enc"
        assert loaded.status == SessionStatus.PAUSED
        assert loaded.context_window == 42
        assert loaded.active_conversation_id == session.active_conversation_id

        conv = loaded.active_conversation()
        assert conv is not None
        assert len(conv.messages) == 2
        assert conv.active_concept == "lhs:phys.force"
        assert conv.tutoring_mode == "direct_instruction"
        assert [m.role for m in conv.messages] == [MessageRole.USER, MessageRole.TOOL]

        user_msg = conv.messages[0]
        assert user_msg.provenance is not None
        assert user_msg.provenance.source == "lhs:phys.force"
        assert user_msg.provenance.grounded is True
        assert user_msg.provenance.entity_ids == ("lhs:phys.force", "lhs:phys.mass")
        assert user_msg.provenance.review_status == "draft"
        assert user_msg.provenance.metadata == {"model": "teacher-v1", "n": 3}
        assert user_msg.tool_calls == ({"name": "search", "args": {"q": "force"}},)
        assert user_msg.tool_results == ({"ok": True},)
        assert user_msg.metadata == {"channel": "web"}
        assert conv.messages[1].provenance is None

        store.delete(session.session_id)
        assert store.list_ids() == []
        assert store.load(session.session_id) is None

    def test_load_unknown_returns_none(self, tmp_path: Path) -> None:
        store = JsonSessionStore(tmp_path / "sessions")
        assert store.load("sess-nope") is None

    def test_list_ids_sorted_and_stem_only(self, tmp_path: Path) -> None:
        store = JsonSessionStore(tmp_path / "sessions")
        for sid in ("sess-b", "sess-a", "sess-c"):
            store.save(Session(learner_id="l", session_id=sid))
        assert store.list_ids() == ["sess-a", "sess-b", "sess-c"]
        # Non-session JSON files are ignored / stemmed the same way.
        (tmp_path / "sessions" / "other.json").write_text("{}", encoding="utf-8")
        assert store.list_ids() == ["other", "sess-a", "sess-b", "sess-c"]

    def test_delete_missing_ok(self, tmp_path: Path) -> None:
        store = JsonSessionStore(tmp_path / "sessions")
        store.delete("sess-never-saved")  # must not raise

    def test_creates_directory(self, tmp_path: Path) -> None:
        JsonSessionStore(tmp_path / "deep" / "nested" / "sessions")
        assert (tmp_path / "deep" / "nested" / "sessions").is_dir()

    def test_corrupt_json_returns_none(self, tmp_path: Path) -> None:
        store = JsonSessionStore(tmp_path / "sessions")
        store.save(Session(learner_id="l", session_id="sess-corrupt"))
        (tmp_path / "sessions" / "sess-corrupt.json").write_text(
            "{not valid json", encoding="utf-8"
        )
        assert store.load("sess-corrupt") is None
        # list_ids still reports the file; only load is defensive.
        assert "sess-corrupt" in store.list_ids()


class TestInMemorySessionStore:
    def test_save_load_list_delete(self) -> None:
        store = InMemorySessionStore()
        s1 = Session(learner_id="l", session_id="sess-1")
        s2 = Session(learner_id="l", session_id="sess-2")
        store.save(s1)
        store.save(s2)
        assert store.load("sess-1") is s1
        assert store.list_ids() == ["sess-1", "sess-2"]
        store.delete("sess-1")
        assert store.load("sess-1") is None
        assert store.list_ids() == ["sess-2"]
        # Deleting an unknown id is a no-op.
        store.delete("sess-missing")


class TestEncodeHelpers:
    def test_encode_enum_datetime_dict_list(self) -> None:
        assert _encode(MessageRole.USER) == "user"
        assert _encode(SessionStatus.ENDED) == "ended"
        dt = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)
        assert _encode(dt) == "2024-01-02T03:04:05+00:00"
        assert _encode({2: "two", 3: "three"}) == {"2": "two", "3": "three"}
        assert _encode([{"a": MessageRole.TOOL}, ("b",)]) == [
            {"a": "tool"},
            ["b"],
        ]

    def test_encode_scalars_pass_through(self) -> None:
        assert _encode(None) is None
        assert _encode(1) == 1
        assert _encode("x") == "x"
        assert _encode(True) is True

    def test_session_to_dict_flat(self) -> None:
        session = Session(learner_id="l", session_id="sess-enc")
        d = _session_to_dict(session)
        assert d["learner_id"] == "l"
        assert d["session_id"] == "sess-enc"
        assert d["status"] == "active"
        assert isinstance(d["created_at"], str)
        assert d["context_window"] == 20
        assert d["conversations"] == []
        assert d["active_conversation_id"] is None

    def test_session_to_dict_raises_on_non_dict_encode(self) -> None:
        # _session_to_dict trusts _encode returns a dict; force the guard by
        # monkeypatching to a scalar.
        from app.session import session_manager as sm

        original = sm._encode
        try:
            sm._encode = lambda obj: 5
            with pytest.raises(TypeError):
                _session_to_dict(Session(learner_id="l"))
        finally:
            sm._encode = original

    def test_session_from_dict_round_trip(self) -> None:
        session = _session_with_conversation()
        rebuilt = _session_from_dict(_session_to_dict(session))
        # Reconstruction is intentionally lossy for datetimes (created_at,
        # updated_at, last_activity_at, message timestamps are not persisted),
        # so compare the semantic fields.
        assert rebuilt.session_id == session.session_id
        assert rebuilt.learner_id == session.learner_id
        assert rebuilt.status == session.status
        assert rebuilt.context_window == session.context_window
        assert rebuilt.active_conversation_id == session.active_conversation_id
        assert rebuilt.metadata == session.metadata

        orig_conv = session.active_conversation()
        new_conv = rebuilt.active_conversation()
        assert orig_conv is not None and new_conv is not None
        assert new_conv.conversation_id == orig_conv.conversation_id
        assert new_conv.session_id == orig_conv.session_id
        assert new_conv.active_concept == orig_conv.active_concept
        assert new_conv.tutoring_mode == orig_conv.tutoring_mode
        assert new_conv.metadata == orig_conv.metadata
        # Message timestamps are not persisted, so compare semantic fields.
        assert [m.role for m in new_conv.messages] == [m.role for m in orig_conv.messages]
        assert [m.content for m in new_conv.messages] == [m.content for m in orig_conv.messages]
        assert [m.message_id for m in new_conv.messages] == [
            m.message_id for m in orig_conv.messages
        ]
        assert [m.provenance for m in new_conv.messages] == [
            m.provenance for m in orig_conv.messages
        ]
        assert [m.tool_calls for m in new_conv.messages] == [
            m.tool_calls for m in orig_conv.messages
        ]
        assert [m.tool_results for m in new_conv.messages] == [
            m.tool_results for m in orig_conv.messages
        ]
        assert [m.metadata for m in new_conv.messages] == [m.metadata for m in orig_conv.messages]

    def test_session_from_dict_empty_session(self) -> None:
        session = Session(learner_id="l", session_id="sess-empty")
        rebuilt = _session_from_dict(_session_to_dict(session))
        assert rebuilt.learner_id == "l"
        assert rebuilt.session_id == "sess-empty"
        assert rebuilt.status == SessionStatus.ACTIVE
        assert rebuilt.conversations == ()
        assert rebuilt.active_conversation_id is None
        assert rebuilt.context_window == 20

    def test_session_from_dict_missing_fields_use_defaults(self) -> None:
        data = {"learner_id": "l", "session_id": "sess-x"}
        rebuilt = _session_from_dict(data)
        assert rebuilt.status == SessionStatus.ACTIVE
        assert rebuilt.conversations == ()
        assert rebuilt.context_window == 20
        assert rebuilt.metadata == {}

    def test_session_from_dict_message_without_provenance(self) -> None:
        session = Session(learner_id="l", session_id="sess-noprov")
        session = session.add_message(Message(role=MessageRole.USER, content="hi"))
        rebuilt = _session_from_dict(_session_to_dict(session))
        conv = rebuilt.active_conversation()
        assert conv is not None
        assert conv.messages[0].provenance is None

    def test_session_from_dict_multiple_conversations(self) -> None:
        base = Session(learner_id="l", session_id="sess-multi")
        base = base.add_message(Message(role=MessageRole.USER, content="first"))
        first_conv = base.active_conversation()
        assert first_conv is not None
        second = Conversation(
            session_id="sess-multi",
            messages=(Message(role=MessageRole.USER, content="second"),),
        )
        base = base.add_conversation(second)
        assert len(base.conversations) == 2
        # active_conversation_id points at the newest conversation.
        assert base.active_conversation_id == second.conversation_id
        rebuilt = _session_from_dict(_session_to_dict(base))
        assert len(rebuilt.conversations) == 2
        assert rebuilt.active_conversation_id == second.conversation_id
        assert [c.messages[0].content for c in rebuilt.conversations] == ["first", "second"]


class TestManagerLifecycleTransitions:
    def test_resume_active_is_noop(self) -> None:
        m = _manager()
        s = m.create("learner-1")
        resumed = m.resume(s.session_id)
        assert resumed.status == SessionStatus.ACTIVE

    def test_resume_paused_reactivates_and_persists(self) -> None:
        store = InMemorySessionStore()
        m = SessionManager(store)
        s = m.create("learner-1")
        # Pause manually through domain immutability.
        paused = s.with_status(SessionStatus.PAUSED)
        store.save(paused)
        resumed = m.resume(s.session_id)
        assert resumed.status == SessionStatus.ACTIVE
        assert m.get(s.session_id).status == SessionStatus.ACTIVE

    def test_archive_marks_archived(self) -> None:
        m = _manager()
        s = m.create("learner-1")
        archived = m.archive(s.session_id)
        assert archived.status == SessionStatus.ARCHIVED
        assert m.get(s.session_id).status == SessionStatus.ARCHIVED

    def test_delete_removes_from_live_and_store(self) -> None:
        store = InMemorySessionStore()
        m = SessionManager(store)
        s = m.create("learner-1")
        m.delete(s.session_id)
        with pytest.raises(SessionNotFoundError):
            m.get(s.session_id)
        assert store.load(s.session_id) is None

    def test_delete_missing_is_noop(self) -> None:
        m = _manager()
        m.delete("sess-never-existed")

    def test_get_loads_from_store_when_not_live(self) -> None:
        store = InMemorySessionStore()
        m = SessionManager(store)
        s = m.create("learner-1")
        # Serve from a brand-new manager backed by the same store (nothing live).
        m2 = SessionManager(store)
        assert m2._live == {}
        fetched = m2.get(s.session_id)
        assert fetched.session_id == s.session_id

    def test_list_active_excludes_archived_and_paused(self) -> None:
        m = _manager()
        a = m.create("l1")
        b = m.create("l2")
        m.archive(a.session_id)
        m.end(b.session_id)
        assert m.list_active() == []


class TestManagerMessagingEdges:
    def test_record_user_with_provenance(self) -> None:
        m = _manager()
        s = m.create("learner-1")
        prov = Provenance(source="user_input", grounded=False, metadata={"x": 1})
        m.record_user(s.session_id, "hello", provenance=prov)
        conv = m.get(s.session_id).active_conversation()
        assert conv is not None
        assert conv.messages[0].provenance is prov

    def test_record_assistant_grounded_creates_provenance(self) -> None:
        m = _manager()
        s = m.create("learner-1")
        m.record_assistant(s.session_id, "grounded answer", grounded=True)
        conv = m.get(s.session_id).active_conversation()
        assert conv is not None
        msg = conv.messages[0]
        assert msg.provenance is not None
        assert msg.provenance.source == "brain"
        assert msg.provenance.grounded is True
        assert msg.is_grounded()

    def test_record_assistant_ungrounded_no_provenance(self) -> None:
        m = _manager()
        s = m.create("learner-1")
        m.record_assistant(s.session_id, "plain answer")
        conv = m.get(s.session_id).active_conversation()
        assert conv is not None
        assert conv.messages[0].provenance is None

    def test_append_persists_to_shared_store(self) -> None:
        store = InMemorySessionStore()
        m = SessionManager(store)
        s = m.create("learner-1")
        m.record_user(s.session_id, "remember this")
        m2 = SessionManager(store)
        conv = m2.get(s.session_id).active_conversation()
        assert conv is not None
        assert conv.messages[0].content == "remember this"

    def test_record_on_unknown_raises(self) -> None:
        m = _manager()
        with pytest.raises(SessionNotFoundError):
            m.record_user("sess-missing", "hello")


class TestManagerContextWindow:
    def test_context_empty_session_returns_empty(self) -> None:
        m = _manager()
        s = m.create("learner-1")
        assert m.context(s.session_id, limit=16) == []

    def test_context_limit_greater_than_messages(self) -> None:
        m = _manager()
        s = m.create("learner-1")
        m.record_user(s.session_id, "only one")
        ctx = m.context(s.session_id, limit=100)
        assert [msg.content for msg in ctx] == ["only one"]

    def test_context_uses_active_conversation(self) -> None:
        m = _manager()
        s = m.create("learner-1")
        m.record_user(s.session_id, "first")
        second = Conversation(
            session_id=s.session_id,
            messages=(Message(role=MessageRole.USER, content="second"),),
        )
        s = s.add_conversation(second)
        # Overwrite the live+stored session with the multi-conversation one.
        m._persist(s)
        ctx = m.context(s.session_id, limit=16)
        assert [msg.content for msg in ctx] == ["second"]
