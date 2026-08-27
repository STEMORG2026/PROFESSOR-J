"""Unit tests for app.domain.session — messages, conversations, sessions."""

from __future__ import annotations

import pytest
from datetime import datetime

from app.domain.session import (
    Conversation,
    Message,
    MessageRole,
    Provenance,
    Session,
    SessionStatus,
)


def _msg(role: MessageRole, content: str, *, grounded: bool = False) -> Message:
    """Build a message, optionally with grounded provenance."""
    prov = Provenance(source="lhs:test", grounded=grounded) if grounded else None
    return Message(role=role, content=content, provenance=prov)


class TestMessage:
    def test_auto_id(self):
        m = Message(role=MessageRole.USER, content="hi")
        assert m.message_id.startswith("msg-")
        assert isinstance(m.timestamp, datetime)

    def test_is_grounded_true(self):
        assert _msg(MessageRole.USER, "x", grounded=True).is_grounded() is True

    def test_is_grounded_false_no_provenance(self):
        assert _msg(MessageRole.USER, "x").is_grounded() is False

    def test_is_grounded_false_unproven_provenance(self):
        m = Message(
            role=MessageRole.USER,
            content="x",
            provenance=Provenance(source="lhs:test", grounded=False),
        )
        assert m.is_grounded() is False

    def test_roles(self):
        assert MessageRole.SYSTEM.value == "system"
        assert MessageRole.ASSISTANT.value == "assistant"
        assert MessageRole.TOOL.value == "tool"


class TestConversation:
    def test_defaults(self):
        c = Conversation(session_id="s1")
        assert c.conversation_id.startswith("conv-")
        assert c.messages == ()
        assert c.active_concept is None
        assert c.tutoring_mode == "socratic_mentor"

    def test_add_message_appends(self):
        c = Conversation(session_id="s1")
        c2 = c.add_message(_msg(MessageRole.USER, "hello"))
        assert len(c2.messages) == 1
        assert c2.messages[0].content == "hello"
        # Original unchanged (immutability)
        assert c.messages == ()

    def test_with_active_concept(self):
        c = Conversation(session_id="s1")
        c2 = c.with_active_concept("lhs:phys.force")
        assert c2.active_concept == "lhs:phys.force"
        assert c.active_concept is None
        c3 = c2.with_active_concept(None)
        assert c3.active_concept is None

    def test_with_tutoring_mode(self):
        c = Conversation(session_id="s1")
        c2 = c.with_tutoring_mode("exam_drill")
        assert c2.tutoring_mode == "exam_drill"
        assert c.tutoring_mode == "socratic_mentor"

    def test_last_user_message(self):
        c = Conversation(
            session_id="s1",
            messages=(
                _msg(MessageRole.USER, "q1"),
                _msg(MessageRole.ASSISTANT, "a1"),
                _msg(MessageRole.USER, "q2"),
            ),
        )
        last = c.last_user_message
        assert last is not None
        assert last.content == "q2"

    def test_last_user_message_none(self):
        c = Conversation(session_id="s1", messages=(_msg(MessageRole.ASSISTANT, "a1"),))
        assert c.last_user_message is None

    def test_last_assistant_message(self):
        c = Conversation(
            session_id="s1",
            messages=(
                _msg(MessageRole.USER, "q1"),
                _msg(MessageRole.ASSISTANT, "a1"),
                _msg(MessageRole.ASSISTANT, "a2"),
            ),
        )
        last = c.last_assistant_message
        assert last is not None
        assert last.content == "a2"

    def test_last_assistant_message_none(self):
        c = Conversation(session_id="s1", messages=(_msg(MessageRole.USER, "q1"),))
        assert c.last_assistant_message is None

    def test_add_message_keeps_updated_at(self):
        c0 = Conversation(session_id="s1")
        c1 = c0.with_active_concept("x")
        assert c1.active_concept == "x"


def _session_with_conv(conv: Conversation) -> Session:
    return Session(learner_id="l1").add_conversation(conv)


class TestSession:
    def test_defaults(self):
        s = Session(learner_id="l1")
        assert s.session_id.startswith("sess-")
        assert s.status == SessionStatus.ACTIVE
        assert s.conversations == ()
        assert s.active_conversation_id is None
        assert s.context_window == 20

    def test_active_conversation_none_when_empty(self):
        assert Session(learner_id="l1").active_conversation() is None

    def test_active_conversation_fallback_most_recent(self):
        c1 = Conversation(session_id="s1")
        c2 = Conversation(session_id="s1")
        s = Session(learner_id="l1", conversations=(c1, c2))
        assert s.active_conversation() is c2

    def test_active_conversation_by_id(self):
        c1 = Conversation(session_id="s1")
        s = Session(
            learner_id="l1",
            conversations=(c1,),
            active_conversation_id=c1.conversation_id,
        )
        assert s.active_conversation() is c1

    def test_active_conversation_fallback_when_id_not_found(self):
        c1 = Conversation(session_id="s1")
        # active_conversation_id points to a conversation NOT in the tuple → falls back to most recent
        s = Session(
            learner_id="l1", conversations=(c1,), active_conversation_id="conv-missing"
        )
        assert s.active_conversation() is c1

    def test_add_conversation_sets_active(self):
        c = Conversation(session_id="s1")
        s = Session(learner_id="l1").add_conversation(c)
        assert s.active_conversation_id == c.conversation_id
        assert s.active_conversation() is c
        # Original unchanged
        assert Session(learner_id="l1").conversations == ()

    def test_set_active_conversation(self):
        c1 = Conversation(session_id="s1")
        c2 = Conversation(session_id="s1")
        s = Session(
            learner_id="l1",
            conversations=(c1, c2),
            active_conversation_id=c1.conversation_id,
        )
        s2 = s.set_active_conversation(c2.conversation_id)
        assert s2.active_conversation() is c2

    def test_with_status(self):
        s = Session(learner_id="l1")
        s2 = s.with_status(SessionStatus.PAUSED)
        assert s2.status == SessionStatus.PAUSED
        assert s.status == SessionStatus.ACTIVE

    def test_with_metadata(self):
        s = Session(learner_id="l1", metadata={"a": 1})
        s2 = s.with_metadata(b=2)
        assert s2.metadata == {"a": 1, "b": 2}
        # Original unchanged
        assert s.metadata == {"a": 1}

    def test_add_message_creates_conversation_when_none(self):
        s = Session(learner_id="l1").add_message(_msg(MessageRole.USER, "hi"))
        assert len(s.conversations) == 1
        assert s.conversations[0].messages[0].content == "hi"
        assert s.active_conversation_id == s.conversations[0].conversation_id

    def test_add_message_appends_to_active(self):
        conv = Conversation(
            session_id="s1", messages=(_msg(MessageRole.USER, "first"),)
        )
        s = Session(
            learner_id="l1",
            conversations=(conv,),
            active_conversation_id=conv.conversation_id,
        )
        s2 = s.add_message(_msg(MessageRole.ASSISTANT, "reply"))
        assert len(s2.conversations) == 1
        assert len(s2.conversations[0].messages) == 2
        assert s2.conversations[0].messages[1].content == "reply"
        # Original session unchanged
        assert len(s.conversations[0].messages) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
