"""Defect-sensitivity tests for the session and conversation model.

**Why this file exists.** `app/domain/session.py` scored **27.9%** on mutation testing (48 killed,
124 survived) — the weakest file in the domain layer and the weakest measured anywhere in this
audit — while sitting at 100% line coverage. `Session` holds conversation state, the active-
conversation pointer and the session lifecycle: the product's dialogue backbone.

The surviving mutants clustered in exactly six methods:

| Survivors | Method |
|---|---|
| 19 | `Session.add_message` |
| 17 | `Session.set_active_conversation` |
| 17 | `Session.with_status` |
| 17 | `Session.with_metadata` |
| 15 | `Session.add_conversation` |
| 13 | `Conversation.add_message` |
| 13 | `Conversation.with_active_concept` |
| 13 | `Conversation.with_tutoring_mode` |

Each is a frozen-dataclass update that re-lists every field by hand. The existing tests asserted the
one field under change and never compared the rest, so any mutation to a preserved field — or to the
update's *semantics* — went unnoticed. These tests compare whole objects and assert behaviour that a
field-flip cannot survive.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.domain.session import (
    Conversation,
    Message,
    MessageRole,
    Provenance,
    Session,
    SessionStatus,
)

BASE_TIME = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def _message(role: MessageRole = MessageRole.USER, content: str = "hello") -> Message:
    return Message(role=role, content=content)


def _conversation(conversation_id: str = "conv-1") -> Conversation:
    return Conversation(
        session_id="sess-1",
        conversation_id=conversation_id,
        created_at=BASE_TIME,
        metadata={"topic": "forces"},
    )


def _session() -> Session:
    return Session(
        learner_id="l1",
        session_id="sess-1",
        conversations=(_conversation("conv-1"),),
        active_conversation_id="conv-1",
        context_window=20,
        created_at=BASE_TIME,
        metadata={"tenant": "school-a"},
    )


# ── Conversation updates ─────────────────────────────────────────────────────


class TestConversationUpdates:
    def test_add_message_appends_and_preserves_everything_else(self) -> None:
        base = _conversation()
        msg = _message()
        updated = base.add_message(msg)
        assert updated.messages == (msg,)
        assert updated.conversation_id == base.conversation_id
        assert updated.session_id == base.session_id
        assert updated.active_concept == base.active_concept
        assert updated.tutoring_mode == base.tutoring_mode
        assert updated.created_at == base.created_at
        assert updated.metadata == base.metadata

    def test_add_message_is_pure_and_accumulates_in_order(self) -> None:
        base = _conversation()
        first, second = _message(content="one"), _message(content="two")
        chained = base.add_message(first).add_message(second)
        assert [m.content for m in chained.messages] == ["one", "two"]
        assert base.messages == ()

    def test_with_active_concept_sets_and_clears(self) -> None:
        base = _conversation()
        assert base.with_active_concept("lhs:phys.force").active_concept == "lhs:phys.force"
        assert base.with_active_concept(None).active_concept is None

    def test_with_active_concept_preserves_everything_else(self) -> None:
        base = _conversation()
        updated = base.with_active_concept("c1")
        assert updated.conversation_id == base.conversation_id
        assert updated.session_id == base.session_id
        assert updated.messages == base.messages
        assert updated.tutoring_mode == base.tutoring_mode
        assert updated.created_at == base.created_at
        assert updated.metadata == base.metadata

    def test_with_tutoring_mode_changes_only_the_mode(self) -> None:
        base = _conversation()
        updated = base.with_tutoring_mode("direct_instruction")
        assert updated.tutoring_mode == "direct_instruction"
        assert updated.conversation_id == base.conversation_id
        assert updated.messages == base.messages
        assert updated.active_concept == base.active_concept
        assert updated.metadata == base.metadata

    def test_updates_advance_updated_at_but_not_created_at(self) -> None:
        base = _conversation()
        updated = base.add_message(_message())
        assert updated.created_at == base.created_at
        assert updated.updated_at >= base.updated_at

    def test_last_user_message_returns_the_most_recent_user_turn(self) -> None:
        conv = (
            _conversation()
            .add_message(_message(MessageRole.USER, "first"))
            .add_message(_message(MessageRole.ASSISTANT, "reply"))
            .add_message(_message(MessageRole.USER, "second"))
        )
        last = conv.last_user_message
        assert last is not None and last.content == "second"

    def test_last_assistant_message_returns_the_most_recent_reply(self) -> None:
        conv = (
            _conversation()
            .add_message(_message(MessageRole.USER, "q"))
            .add_message(_message(MessageRole.ASSISTANT, "a1"))
            .add_message(_message(MessageRole.ASSISTANT, "a2"))
        )
        last = conv.last_assistant_message
        assert last is not None and last.content == "a2"

    def test_last_message_properties_are_none_when_absent(self) -> None:
        conv = _conversation().add_message(_message(MessageRole.USER, "only user"))
        assert conv.last_user_message is not None
        assert conv.last_assistant_message is None
        assert _conversation().last_user_message is None
        assert _conversation().last_assistant_message is None


# ── Session lifecycle updates ────────────────────────────────────────────────


class TestSessionUpdatesPreserveUnrelatedFields:
    """All five `Session` updates must preserve the fields they are not changing."""

    def test_add_conversation_appends_and_activates_it(self) -> None:
        base = _session()
        new = _conversation("conv-2")
        updated = base.add_conversation(new)
        assert [c.conversation_id for c in updated.conversations] == ["conv-1", "conv-2"]
        assert updated.active_conversation_id == "conv-2"
        assert updated.active_conversation() == new

    def test_add_conversation_preserves_session_fields(self) -> None:
        base = _session()
        updated = base.add_conversation(_conversation("conv-2"))
        assert updated.session_id == base.session_id
        assert updated.learner_id == base.learner_id
        assert updated.status == base.status
        assert updated.context_window == base.context_window
        assert updated.created_at == base.created_at
        assert updated.metadata == base.metadata

    def test_add_conversation_is_pure(self) -> None:
        base = _session()
        base.add_conversation(_conversation("conv-2"))
        assert len(base.conversations) == 1

    def test_set_active_conversation_moves_the_pointer(self) -> None:
        base = _session().add_conversation(_conversation("conv-2"))
        moved = base.set_active_conversation("conv-1")
        assert moved.active_conversation_id == "conv-1"
        assert moved.active_conversation() is not None
        assert moved.active_conversation().conversation_id == "conv-1"  # type: ignore[union-attr]

    def test_set_active_conversation_preserves_conversations_and_fields(self) -> None:
        base = _session().add_conversation(_conversation("conv-2"))
        moved = base.set_active_conversation("conv-1")
        assert moved.conversations == base.conversations
        assert moved.status == base.status
        assert moved.context_window == base.context_window
        assert moved.metadata == base.metadata

    def test_with_status_changes_only_status(self) -> None:
        base = _session()
        for status in (
            SessionStatus.PAUSED,
            SessionStatus.ENDED,
            SessionStatus.ARCHIVED,
            SessionStatus.ACTIVE,
        ):
            updated = base.with_status(status)
            assert updated.status == status
            assert updated.conversations == base.conversations
            assert updated.active_conversation_id == base.active_conversation_id
            assert updated.context_window == base.context_window
            assert updated.metadata == base.metadata

    def test_with_status_is_pure(self) -> None:
        base = _session()
        base.with_status(SessionStatus.ENDED)
        assert base.status == SessionStatus.ACTIVE

    def test_with_metadata_merges_rather_than_replacing(self) -> None:
        """New keys are added; existing keys are preserved unless overridden."""
        updated = _session().with_metadata(stage="review", tenant="school-b")
        assert updated.metadata == {"tenant": "school-b", "stage": "review"}

    def test_with_metadata_preserves_unrelated_sets(self) -> None:
        updated = _session().with_metadata(stage="review")
        assert updated.metadata["tenant"] == "school-a"
        assert updated.metadata["stage"] == "review"

    def test_with_metadata_preserves_every_other_field(self) -> None:
        base = _session()
        updated = base.with_metadata(x=1)
        assert updated.session_id == base.session_id
        assert updated.learner_id == base.learner_id
        assert updated.status == base.status
        assert updated.conversations == base.conversations
        assert updated.active_conversation_id == base.active_conversation_id
        assert updated.context_window == base.context_window

    def test_updates_touch_last_activity(self) -> None:
        base = _session()
        for updated in (
            base.set_active_conversation("conv-1"),
            base.with_status(SessionStatus.PAUSED),
            base.with_metadata(x=1),
        ):
            assert updated.last_activity_at >= base.last_activity_at
            assert updated.updated_at >= base.updated_at


# ── add_message: the routing behaviour ───────────────────────────────────────


class TestSessionAddMessage:
    """`add_message` routes into the active conversation, or creates one."""

    def test_message_lands_in_the_active_conversation(self) -> None:
        session = _session()
        msg = _message(content="routed")
        updated = session.add_message(msg)
        assert len(updated.conversations) == 1
        assert updated.conversations[0].messages == (msg,)
        assert updated.active_conversation_id == "conv-1"

    def test_inactive_conversations_are_untouched(self) -> None:
        """Adding a message must modify only the active conversation."""
        session = (
            _session().add_conversation(_conversation("conv-2")).set_active_conversation("conv-1")
        )
        updated = session.add_message(_message(content="to conv-1"))
        by_id = {c.conversation_id: c for c in updated.conversations}
        assert [m.content for m in by_id["conv-1"].messages] == ["to conv-1"]
        assert by_id["conv-2"].messages == ()

    def test_creates_a_conversation_when_none_is_active(self) -> None:
        bare = Session(learner_id="l1", session_id="sess-9")
        msg = _message(content="first ever")
        updated = bare.add_message(msg)
        assert len(updated.conversations) == 1
        assert updated.conversations[0].messages == (msg,)
        assert updated.active_conversation_id == updated.conversations[0].conversation_id

    def test_message_order_is_preserved_across_updates(self) -> None:
        session = _session()
        for text in ("one", "two", "three"):
            session = session.add_message(_message(content=text))
        assert [m.content for m in session.conversations[0].messages] == ["one", "two", "three"]

    def test_preserves_session_level_fields(self) -> None:
        base = _session()
        updated = base.add_message(_message())
        assert updated.session_id == base.session_id
        assert updated.learner_id == base.learner_id
        assert updated.status == base.status
        assert updated.context_window == base.context_window
        assert updated.metadata == base.metadata

    def test_is_pure(self) -> None:
        base = _session()
        base.add_message(_message())
        assert base.conversations[0].messages == ()


# ── active_conversation: pointer resolution ──────────────────────────────────


class TestActiveConversationResolution:
    def test_resolves_the_pointer(self) -> None:
        assert _session().active_conversation() is not None
        assert _session().active_conversation().conversation_id == "conv-1"  # type: ignore[union-attr]

    def test_falls_back_to_the_most_recent_when_no_pointer_is_set(self) -> None:
        """Documented behaviour: with no pointer, the most recent conversation is used."""
        session = Session(learner_id="l1", conversations=(_conversation("c1"), _conversation("c2")))
        resolved = session.active_conversation()
        assert resolved is not None
        assert resolved.conversation_id == "c2"

    def test_returns_none_when_there_are_no_conversations(self) -> None:
        assert Session(learner_id="l1").active_conversation() is None

    def test_pointer_takes_precedence_over_recency(self) -> None:
        """With a valid pointer set, the most recent conversation is NOT used."""
        session = Session(
            learner_id="l1",
            conversations=(_conversation("c1"), _conversation("c2")),
            active_conversation_id="c1",
        )
        resolved = session.active_conversation()
        assert resolved is not None
        assert resolved.conversation_id == "c1"

    def test_dangling_pointer_silently_falls_back_to_the_most_recent(self) -> None:
        """Pins a real design risk rather than asserting it away.

        `active_conversation()` falls back to `conversations[-1]` when the pointer does not match
        any conversation. So a stale or mistyped `active_conversation_id` does not surface as an
        error — it silently routes to a *different* conversation. This test records that behaviour
        so a future change to either fallback or validation is a deliberate, visible decision.
        """
        dangling = Session(
            learner_id="l1",
            conversations=(_conversation("c1"), _conversation("c2")),
            active_conversation_id="does-not-exist",
        )
        resolved = dangling.active_conversation()
        assert resolved is not None
        assert resolved.conversation_id == "c2"

    def test_set_active_conversation_does_not_validate_the_id(self) -> None:
        """`set_active_conversation` accepts an unknown id without complaint.

        Combined with the fallback above, an unknown id yields the most recent conversation
        rather than an error. Recorded as observed behaviour; whether it should raise is a
        product decision, not a test decision.
        """
        session = _session().set_active_conversation("no-such-conversation")
        assert session.active_conversation_id == "no-such-conversation"
        assert session.active_conversation() is not None


# ── Provenance ───────────────────────────────────────────────────────────────


class TestProvenance:
    def test_grounded_message_reports_grounded(self) -> None:
        msg = Message(
            role=MessageRole.ASSISTANT,
            content="F = m·a",
            provenance=Provenance(
                source="lhs:phys.force", grounded=True, entity_ids=("lhs:phys.force",)
            ),
        )
        assert msg.is_grounded() is True

    def test_message_without_provenance_is_not_grounded(self) -> None:
        assert _message().is_grounded() is False

    def test_ungrounded_provenance_is_not_grounded(self) -> None:
        msg = Message(
            role=MessageRole.ASSISTANT,
            content="general",
            provenance=Provenance(source="general_knowledge", grounded=False),
        )
        assert msg.is_grounded() is False


# ── Determinism and identity ─────────────────────────────────────────────────


class TestIdentifierGeneration:
    def test_generated_ids_are_unique_across_instances(self) -> None:
        ids = {Conversation(session_id="s").conversation_id for _ in range(50)}
        assert len(ids) == 50

    def test_generated_session_ids_are_unique(self) -> None:
        ids = {Session(learner_id="l").session_id for _ in range(50)}
        assert len(ids) == 50

    def test_explicit_ids_are_honoured(self) -> None:
        assert _conversation("conv-x").conversation_id == "conv-x"
        assert Session(learner_id="l", session_id="sess-x").session_id == "sess-x"
