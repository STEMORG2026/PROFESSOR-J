"""Tests for the JARVIS-parity utility layer: event bus, context window, prompt loader."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.context import ContextStats, ContextWindowManager
from app.context.tokenizer import get_token_counter
from app.events import Event, HITLRequestEvent, InMemoryAsyncBus, TelemetryEvent
from app.prompt import PromptLoader, PromptTemplateError


# ── event bus ────────────────────────────────────────────────────────────
class TestEventBus:
    def test_subscribe_and_publish_async(self) -> None:
        bus = InMemoryAsyncBus()
        received: list[str] = []

        async def handler(event: Event) -> None:
            received.append(event.event_type)

        bus.subscribe("telemetry", handler)

        async def runner() -> None:
            await bus.publish_async(TelemetryEvent(category="test", data={"x": 1}))

        asyncio.run(runner())
        assert received == ["telemetry"]

    def test_wildcard_subscriber(self) -> None:
        bus = InMemoryAsyncBus()
        seen: list[str] = []

        async def wildcard(event: Event) -> None:
            seen.append(event.event_type)

        bus.subscribe("*", wildcard)
        target = TelemetryEvent(category="test")

        async def runner() -> None:
            await bus.publish_async(target)

        asyncio.run(runner())
        assert "telemetry" in seen

    def test_handler_exception_does_not_propagate(self) -> None:
        bus = InMemoryAsyncBus()

        async def bad_handler(event: Event) -> None:
            raise RuntimeError("boom")

        bus.subscribe("telemetry", bad_handler)

        async def runner() -> None:
            await bus.publish_async(TelemetryEvent())  # should not raise

        asyncio.run(runner())  # must not raise

    def test_unsubscribe(self) -> None:
        bus = InMemoryAsyncBus()
        calls: list[str] = []

        async def handler(event: Event) -> None:
            calls.append(event.event_type)

        bus.subscribe("telemetry", handler)
        bus.unsubscribe("telemetry", handler)

        async def runner() -> None:
            await bus.publish_async(TelemetryEvent(category="x"))

        asyncio.run(runner())
        assert calls == []

    def test_typed_event_to_dict(self) -> None:
        evt = HITLRequestEvent(plan_id="p1", step_id="s1", tool_name="run_code")
        data = evt.to_dict()
        assert data["event_type"] == "hitl.request"
        assert data["tool_name"] == "run_code"
        assert "timestamp" in data


# ── context window ───────────────────────────────────────────────────────
class TestContextWindow:
    def _msgs(self, count: int, size: int = 50) -> list[dict[str, str]]:
        msgs: list[dict[str, str]] = [{"role": "system", "content": "You are a tutor."}]
        for i in range(count):
            msgs.append({"role": "user", "content": f"user message {i}" * size})
            msgs.append({"role": "assistant", "content": f"assistant reply {i}" * size})
        return msgs

    def test_keeps_all_when_under_budget(self) -> None:
        cm = ContextWindowManager(max_tokens=10000, safety_margin=0)
        msgs = self._msgs(3)
        fitted = cm.fit(msgs)
        assert len(fitted) == len(msgs)

    def test_trims_oldest_pairs_when_over(self) -> None:
        cm = ContextWindowManager(max_tokens=80, safety_margin=0)
        msgs = self._msgs(20)
        fitted = cm.fit(msgs)
        stats = cm.get_stats()
        assert stats is not None and stats.was_trimmed
        # newest (last) assistant message is preserved
        assert fitted[-1]["role"] == "assistant"
        # system always kept
        assert fitted[0]["role"] == "system"

    def test_system_prompt_always_kept(self) -> None:
        cm = ContextWindowManager(max_tokens=10, safety_margin=0)
        msgs = [
            {"role": "system", "content": "system instructions"},
            {"role": "user", "content": "hi"},
        ]
        fitted = cm.fit(msgs)
        assert fitted[0]["role"] == "system"
        assert fitted[0]["content"] == "system instructions"

    def test_stats_recorded(self) -> None:
        cm = ContextWindowManager(max_tokens=100000, safety_margin=0)
        msgs = self._msgs(5)
        cm.fit(msgs)
        stats: ContextStats | None = cm.get_stats()
        assert stats is not None
        assert stats.messages_kept == len(msgs)
        assert stats.was_trimmed is False

    def test_count_tokens_uses_estimator(self) -> None:
        cm = ContextWindowManager(max_tokens=100000)
        assert cm.count_tokens_text("hello world") > 0

    def test_tokenizer_fallback(self) -> None:
        counter = get_token_counter("default")  # falls back to word-based when no tiktoken
        assert callable(counter)
        assert counter("hello world how are you") > 0


# ── prompt loader ────────────────────────────────────────────────────────
class TestPromptLoader:
    def _setup(self, tmp_path: Path) -> tuple[Path, PromptLoader]:
        (tmp_path / "system_base.md").write_text(
            "You are {role} helping {learner} with {subject}.", encoding="utf-8"
        )
        return tmp_path, PromptLoader(tmp_path)

    def test_render_substitutes(self, tmp_path: Path) -> None:
        _, loader = self._setup(tmp_path)
        out = loader.render("system_base.md", role="tutor", learner="Sajan", subject="physics")
        assert out == "You are tutor helping Sajan with physics."

    def test_required_variables(self, tmp_path: Path) -> None:
        _, loader = self._setup(tmp_path)
        assert loader.get_required_variables("system_base.md") == {"role", "learner", "subject"}

    def test_missing_variable_raises(self, tmp_path: Path) -> None:
        _, loader = self._setup(tmp_path)
        with pytest.raises(PromptTemplateError):
            loader.render("system_base.md", role="tutor")  # missing learner, subject

    def test_missing_template_raises(self, tmp_path: Path) -> None:
        _, loader = self._setup(tmp_path)
        with pytest.raises(PromptTemplateError):
            loader.get_template("nope.md")

    def test_hot_reload_on_mtime_change(self, tmp_path: Path) -> None:
        _, loader = self._setup(tmp_path)
        first = loader.render("system_base.md", role="t", learner="S", subject="p")
        # edit the file
        (tmp_path / "system_base.md").write_text(
            "You are {role} helping {learner} with {subject} (v2).", encoding="utf-8"
        )
        second = loader.render("system_base.md", role="t", learner="S", subject="p")
        assert first != second
        assert "v2" in second
