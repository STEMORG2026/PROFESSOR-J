"""Tests for the cognitive brain pipeline (intent, plan, synthesis)."""

from __future__ import annotations

import pytest

from app.brain.graph import CognitiveBrain, build_brain_graph
from app.brain.intents import Intent, classify_intent
from app.models.catalog import ProviderCatalog
from app.models.providers import MockProvider
from app.models.router import ModelRouter


class TestIntentClassifier:
    def test_direct_chat_default(self) -> None:
        assert classify_intent("hello there") == Intent.DIRECT_CHAT

    def test_tutorial(self) -> None:
        assert classify_intent("teach me Newton's second law") == Intent.TUTORIAL

    def test_file_query(self) -> None:
        assert classify_intent("read notes.md in workspace") == Intent.FILE_QUERY

    def test_tool_search(self) -> None:
        assert classify_intent("run code to sum 1..10") == Intent.TOOL_SEARCH

    def test_multi_step(self) -> None:
        assert (
            classify_intent("first parse input, then filter, then sort")
            == Intent.MULTI_STEP
        )

    def test_empty_prompt_direct_chat(self) -> None:
        assert classify_intent("") == Intent.DIRECT_CHAT


def _router() -> ModelRouter:
    return ModelRouter(ProviderCatalog([MockProvider(name="mock-brain", model="m")]))


class TestBrainGraph:
    @pytest.mark.asyncio
    async def test_runs_end_to_end_with_mock_provider(self) -> None:
        graph = build_brain_graph(_router())
        out = await graph.ainvoke({"prompt": "explain acceleration"})
        assert out["intent"] == Intent.TUTORIAL
        assert out["provider_used"] == "mock-brain"
        assert "[mock:mock-brain]" in out["response"]

    @pytest.mark.asyncio
    async def test_direct_chat_short_pipeline(self) -> None:
        graph = build_brain_graph(_router())
        out = await graph.ainvoke({"prompt": "hi"})
        assert out["intent"] == Intent.DIRECT_CHAT

    @pytest.mark.asyncio
    async def test_run_via_facade(self) -> None:
        brain = CognitiveBrain(router=_router())
        result = await brain.run("teach me how to balance a chemical equation")
        assert result["intent"] == Intent.TUTORIAL.value
        assert result["provider"] == "mock-brain"
        assert "[mock:mock-brain]" in result["response"]

    @pytest.mark.asyncio
    async def test_builds_default_graph_safely(self) -> None:
        graph = build_brain_graph()  # no router -> MockProvider fallback
        out = await graph.ainvoke({"prompt": "run a quick tool"})
        assert out["provider_used"]

    @pytest.mark.asyncio
    async def test_plan_steps_vary_by_intent(self) -> None:
        brain = CognitiveBrain(router=_router())
        assert (await brain.run("read file x"))["plan_steps"] == 1  # FILE_QUERY
        assert (await brain.run("hello"))["plan_steps"] == 1  # DIRECT_CHAT
        assert (await brain.run("teach me force"))["plan_steps"] == 2  # TUTORIAL
