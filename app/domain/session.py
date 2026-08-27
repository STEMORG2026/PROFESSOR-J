"""Session & Conversation Types — Session management and dialogue history."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from app.domain.time import utc_now
from enum import Enum
from typing import Any
from uuid import uuid4


class MessageRole(str, Enum):
    """Role of a message in a conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True, slots=True)
class Provenance:
    """Provenance tracking for a message or response."""

    source: str  # e.g., "lhs:phys.force", "general_knowledge", "mcp:filesystem"
    grounded: bool = False
    entity_ids: tuple[str, ...] = field(default_factory=tuple)
    review_status: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Message:
    """A single message in a conversation."""

    role: MessageRole
    content: str
    message_id: str = field(default_factory=lambda: f"msg-{uuid4().hex[:8]}")
    provenance: Provenance | None = None
    tool_calls: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    tool_results: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    timestamp: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_grounded(self) -> bool:
        """Whether this message has grounded provenance."""
        return self.provenance is not None and self.provenance.grounded


@dataclass(frozen=True, slots=True)
class Conversation:
    """A conversation thread within a session."""

    session_id: str
    conversation_id: str = field(default_factory=lambda: f"conv-{uuid4().hex[:8]}")
    messages: tuple[Message, ...] = field(default_factory=tuple)
    active_concept: str | None = None  # Current concept being discussed
    tutoring_mode: str = "socratic_mentor"
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_message(self, message: Message) -> Conversation:
        """Return new conversation with added message."""
        return Conversation(
            conversation_id=self.conversation_id,
            session_id=self.session_id,
            messages=self.messages + (message,),
            active_concept=self.active_concept,
            tutoring_mode=self.tutoring_mode,
            created_at=self.created_at,
            updated_at=utc_now(),
            metadata=self.metadata,
        )

    def with_active_concept(self, concept_id: str | None) -> Conversation:
        """Return new conversation with updated active concept."""
        return Conversation(
            conversation_id=self.conversation_id,
            session_id=self.session_id,
            messages=self.messages,
            active_concept=concept_id,
            tutoring_mode=self.tutoring_mode,
            created_at=self.created_at,
            updated_at=utc_now(),
            metadata=self.metadata,
        )

    def with_tutoring_mode(self, mode: str) -> Conversation:
        """Return new conversation with updated tutoring mode."""
        return Conversation(
            conversation_id=self.conversation_id,
            session_id=self.session_id,
            messages=self.messages,
            active_concept=self.active_concept,
            tutoring_mode=mode,
            created_at=self.created_at,
            updated_at=utc_now(),
            metadata=self.metadata,
        )

    @property
    def last_user_message(self) -> Message | None:
        """Get the last user message."""
        for msg in reversed(self.messages):
            if msg.role == MessageRole.USER:
                return msg
        return None

    @property
    def last_assistant_message(self) -> Message | None:
        """Get the last assistant message."""
        for msg in reversed(self.messages):
            if msg.role == MessageRole.ASSISTANT:
                return msg
        return None


class SessionStatus(str, Enum):
    """Status of a session."""

    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class Session:
    """
    User session with conversation history and pedagogical context.

    Immutable, serializable, supports pause/resume.
    """

    learner_id: str
    session_id: str = field(default_factory=lambda: f"sess-{uuid4().hex[:8]}")
    status: SessionStatus = SessionStatus.ACTIVE
    conversations: tuple[Conversation, ...] = field(default_factory=tuple)
    active_conversation_id: str | None = None
    context_window: int = 20  # Number of messages to keep in context
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    last_activity_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def active_conversation(self) -> Conversation | None:
        """Get the active conversation."""
        if self.active_conversation_id:
            for conv in self.conversations:
                if conv.conversation_id == self.active_conversation_id:
                    return conv
        # Return most recent if no active set
        return self.conversations[-1] if self.conversations else None

    def add_conversation(self, conversation: Conversation) -> "Session":
        """Return new session with added conversation."""
        return Session(
            session_id=self.session_id,
            learner_id=self.learner_id,
            status=self.status,
            conversations=self.conversations + (conversation,),
            active_conversation_id=conversation.conversation_id,
            context_window=self.context_window,
            created_at=self.created_at,
            updated_at=utc_now(),
            last_activity_at=utc_now(),
            metadata=self.metadata,
        )

    def set_active_conversation(self, conversation_id: str) -> "Session":
        """Set the active conversation."""
        return Session(
            session_id=self.session_id,
            learner_id=self.learner_id,
            status=self.status,
            conversations=self.conversations,
            active_conversation_id=conversation_id,
            context_window=self.context_window,
            created_at=self.created_at,
            updated_at=utc_now(),
            last_activity_at=utc_now(),
            metadata=self.metadata,
        )

    def with_status(self, status: SessionStatus) -> "Session":
        """Return new session with updated status."""
        return Session(
            session_id=self.session_id,
            learner_id=self.learner_id,
            status=status,
            conversations=self.conversations,
            active_conversation_id=self.active_conversation_id,
            context_window=self.context_window,
            created_at=self.created_at,
            updated_at=utc_now(),
            last_activity_at=utc_now(),
            metadata=self.metadata,
        )

    def with_metadata(self, **metadata: Any) -> "Session":
        """Return new session with merged metadata."""
        return Session(
            session_id=self.session_id,
            learner_id=self.learner_id,
            status=self.status,
            conversations=self.conversations,
            active_conversation_id=self.active_conversation_id,
            context_window=self.context_window,
            created_at=self.created_at,
            updated_at=utc_now(),
            last_activity_at=utc_now(),
            metadata={**self.metadata, **metadata},
        )

    def add_message(self, message: Message) -> "Session":
        """Add a message to the active conversation."""
        active = self.active_conversation()
        if not active:
            # Create new conversation
            new_conv = Conversation(
                session_id=self.session_id,
                messages=(message,),
            )
            return self.add_conversation(new_conv)

        new_conv = active.add_message(message)
        new_convs = tuple(
            c if c.conversation_id != active.conversation_id else new_conv
            for c in self.conversations
        )
        return Session(
            session_id=self.session_id,
            learner_id=self.learner_id,
            status=self.status,
            conversations=new_convs,
            active_conversation_id=active.conversation_id,
            context_window=self.context_window,
            created_at=self.created_at,
            updated_at=utc_now(),
            last_activity_at=utc_now(),
            metadata=self.metadata,
        )
