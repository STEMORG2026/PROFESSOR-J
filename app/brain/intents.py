"""Deterministic intent classification for the cognitive brain.

The classifier is rule-based (no LLM) so the brain path is fully testable and
predictable. It maps a user prompt to one of the cognitive intents defined in
the architecture, which the plan builder then expands into an ExecutionPlan.
"""

from __future__ import annotations

import re
from enum import Enum


class Intent(str, Enum):
    DIRECT_CHAT = "direct_chat"
    FILE_QUERY = "file_query"
    TOOL_SEARCH = "tool_search"
    MULTI_STEP = "multi_step"
    TUTORIAL = "tutorial"
    GAME_DEV = "game_dev"


# Signal words, lower-cased. Order matters: more-specific intents are tested
# before general ones.
_GAMEDEV_HINTS = (
    "game dev",
    "gamedev",
    "game project",
    "game engine",
    "rules engine",
    "board game",
    "gameplay",
    "game mechanics",
    "game component",
    "turn-based game",
    "turn based game",
    "dice mechanics",
    "player token",
    "unity game",
    "godot game",
)
_FILE_HINTS = (".txt", ".md", ".py", ".json", ".csv", "file ", "document", "workspace")
_MULTI_STEP_HINTS = (
    "and then",
    "step by step",
    "steps",
    "first ",
    "then ",
    "sequence",
    "plan",
    "1. ",
    "2. ",
)
_TOOL_HINTS = (
    "run code",
    "execute",
    "file system",
    "create file",
    "read file",
    "write file",
    "list files",
    "git",
    "search the web",
)
_TUTORIAL_HINTS = (
    "teach me",
    "explain",
    "tutor",
    "homework",
    "how do i",
    "how does",
    "learn",
    "concept",
    "socratic",
    "newton",
    "equation",
    "solving",
    "practice problem",
)
_DIGIT_STEP = re.compile(r"^\d\.\s", re.MULTILINE)


def classify_intent(prompt: str) -> Intent:
    """Classify a user prompt into a cognitive intent using deterministic rules."""
    if not prompt or not prompt.strip():
        return Intent.DIRECT_CHAT
    low = prompt.lower().strip()

    if any(h in low for h in _GAMEDEV_HINTS):
        return Intent.GAME_DEV

    if any(h in low for h in _TOOL_HINTS):
        return Intent.TOOL_SEARCH

    if any(h in low for h in _FILE_HINTS):
        return Intent.FILE_QUERY

    if any(h in low for h in _TUTORIAL_HINTS) or _DIGIT_STEP.search(low):
        return Intent.TUTORIAL

    if any(h in low for h in _MULTI_STEP_HINTS):
        return Intent.MULTI_STEP

    return Intent.DIRECT_CHAT
