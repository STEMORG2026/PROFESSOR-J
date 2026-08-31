"""Unit test verifying CognitiveBrain intent classification and planning for GameDev."""

import pytest

from app.brain.graph import CognitiveBrain
from app.brain.intents import Intent, classify_intent


def test_classify_intent_gamedev() -> None:
    assert classify_intent("Create a game project for a turn-based board game") == Intent.GAME_DEV
    assert classify_intent("Develop a rules engine with dice mechanics") == Intent.GAME_DEV
    assert classify_intent("I want to build a unity game with pure core logic") == Intent.GAME_DEV
    assert classify_intent("Design a godot game architecture") == Intent.GAME_DEV


@pytest.mark.asyncio
async def test_cognitive_brain_gamedev_flow() -> None:
    brain = CognitiveBrain()
    prompt = "Create a turn-based board game rules engine with dice mechanics for 2 players"

    result = await brain.run(prompt)
    assert result["intent"] == Intent.GAME_DEV.value
    assert result["plan_steps"] >= 3
    assert result["provider"] == "mock"
