"""Typed state shared across the cognitive brain graph."""

from __future__ import annotations

from typing import TypedDict

from app.brain.intents import Intent
from app.domain.plan import ExecutionPlan


class BrainState(TypedDict, total=False):
    """The full state passed between LangGraph nodes."""

    prompt: str
    intent: Intent
    plan: ExecutionPlan
    response: str
    provider_used: str
    grounded: bool
    error: str | None
