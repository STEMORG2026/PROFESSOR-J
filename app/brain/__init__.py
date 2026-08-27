"""Cognitive brain — the multi-agent orchestration pipeline.

Current scope (foundational, fully testable): a LangGraph pipeline of
intent classification -> plan construction -> synthesis through the model
pool. Real tool execution through the safety gate arrives in later phases.
"""

from app.brain.graph import CognitiveBrain, build_brain_graph  # noqa: F401
from app.brain.intents import Intent, classify_intent  # noqa: F401
from app.brain.state import BrainState  # noqa: F401

__all__ = [
    "CognitiveBrain",
    "build_brain_graph",
    "Intent",
    "classify_intent",
    "BrainState",
]
