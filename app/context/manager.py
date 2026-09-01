"""Context window manager — never exceed a model's token limit.

Pattern-inherited from JARVIS ``app/context/manager.py``.

Key design: trims the conversation in user/assistant *pairs*, never individual
messages, preserving conversational coherence. Before calling the LLM: count
tokens, then if over budget trim the oldest pairs first, keeping the newest —
and always keeping the active user prompt.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.context.tokenizer import get_token_counter


@dataclass
class ContextStats:
    """Statistics about the last :meth:`ContextWindowManager.fit` call."""

    total_tokens: int
    max_tokens: int
    utilization: float
    messages_kept: int
    messages_trimmed: int
    pairs_kept: int
    pairs_trimmed: int
    was_trimmed: bool


class ContextWindowManager:
    """Trims message lists to fit a model context window, preserving pairs."""

    # Roles considered "conversation" (system messages are always kept).
    CONVERSATION_ROLES = ("user", "assistant")

    def __init__(
        self,
        max_tokens: int = 4096,
        safety_margin: int = 100,
        token_counter: Callable[[str], int] | None = None,
        model_name: str = "default",
    ) -> None:
        self.max_tokens = max_tokens
        self.safety_margin = safety_margin
        self.effective_max = max_tokens - safety_margin
        self._count_tokens = token_counter or get_token_counter(model_name)
        self.last_stats: ContextStats | None = None

    # ── public API ───────────────────────────────────────────────────────
    def count_tokens(self, messages: list[dict[str, Any]]) -> int:
        """Count tokens in a message list (~4/message for role overhead)."""
        total = 0
        for m in messages:
            total += 4 + self._count_tokens(self._content_to_text(m.get("content")))
        return total

    def count_tokens_text(self, text: str) -> int:
        return self._count_tokens(text)

    def fit(
        self, messages: list[dict[str, Any]], max_tokens: int | None = None
    ) -> list[dict[str, Any]]:
        """Return a copy of ``messages`` that fits the context window.

        System messages are always kept. Conversation messages are grouped into
        user/assistant pairs and oldest pairs are dropped first, so an exchange
        is never split. If even the newest pair overflows, it is kept anyway so
        the active user prompt is never silently dropped.
        """
        limit = max_tokens or self.effective_max
        original_count = len(messages)
        was_trimmed = False

        system_messages = [m for m in messages if m.get("role") == "system"]
        conversation = [m for m in messages if m.get("role") != "system"]

        system_tokens = self.count_tokens(system_messages)
        available = limit - system_tokens

        if available <= 0:
            self.last_stats = ContextStats(
                total_tokens=system_tokens,
                max_tokens=limit,
                utilization=system_tokens / limit if limit else 0.0,
                messages_kept=len(system_messages),
                messages_trimmed=original_count - len(system_messages),
                pairs_kept=0,
                pairs_trimmed=0,
                was_trimmed=True,
            )
            return system_messages

        pairs = self._group_into_pairs(conversation)
        original_pairs = len(pairs)

        fitted_pairs: list[list[dict[str, Any]]] = []
        current_tokens = 0
        for pair in reversed(pairs):
            pair_tokens = self.count_tokens(pair)
            if current_tokens + pair_tokens <= available:
                fitted_pairs.insert(0, pair)
                current_tokens += pair_tokens
            else:
                was_trimmed = True
                if not fitted_pairs:
                    fitted_pairs.insert(0, pair)
                    current_tokens += pair_tokens

        final = system_messages + [msg for pair in fitted_pairs for msg in pair]
        final_tokens = self.count_tokens(final)

        self.last_stats = ContextStats(
            total_tokens=final_tokens,
            max_tokens=limit,
            utilization=final_tokens / limit if limit else 0.0,
            messages_kept=len(final),
            messages_trimmed=original_count - len(final),
            pairs_kept=len(fitted_pairs),
            pairs_trimmed=original_pairs - len(fitted_pairs),
            was_trimmed=was_trimmed,
        )
        return final

    def get_stats(self) -> ContextStats | None:
        return self.last_stats

    def get_tokenizer_info(self) -> dict[str, str]:
        from app.context.tokenizer import get_tokenizer_info

        return get_tokenizer_info()

    # ── internals ────────────────────────────────────────────────────────
    @staticmethod
    def _content_to_text(content: Any) -> str:
        """Coerce message content into a countable string."""
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [b.get("text") or "" for b in content if isinstance(b, dict)]
            return "\n".join(p for p in parts if p)
        return str(content)

    @staticmethod
    def _group_into_pairs(messages: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        """Group messages into user/assistant pairs (never split an exchange)."""
        if not messages:
            return []
        pairs: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = [messages[0]]
        for i in range(1, len(messages)):
            msg = messages[i]
            prev = messages[i - 1]
            current.append(msg)
            if msg.get("role") == "assistant" or (
                msg.get("role") == "user" and prev.get("role") == "user"
            ):
                # end the pair after an assistant message, or orphan a duplicate user
                if msg.get("role") == "user" and prev.get("role") == "user":
                    pairs.append(current[:-1])  # first user orphaned
                    current = [msg]
                else:
                    pairs.append(current)
                    current = []
        if current:
            pairs.append(current)
        return [p for p in pairs if p]


__all__ = ["ContextWindowManager", "ContextStats"]
