"""Cognitive brain — a minimal, testable LangGraph pipeline.

Nodes: intent classification -> plan construction -> synthesis through the
model router. The classifier and planner are deterministic (no LLM), so the
whole graph runs end-to-end against the router's provider pool, including the
deterministic MockProvider used in tests.

This is the foundational shape described in ARCHITECTURE.md (CognitiveBrain
Intent -> Plan -> Execute -> Synthesize). Later phases add real tool execution
through the safety gate and checkpointing.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.brain.intents import Intent, classify_intent
from app.brain.state import BrainState
from app.domain.plan import ExecutionPlan, ExecutionStep, PlanStatus, ToolCallRequest
from app.domain.tool import SafetyTier
from app.models.catalog import ProviderCatalog
from app.models.providers import LLMMessage, MockProvider
from app.models.router import ModelRouter

logger = logging.getLogger(__name__)


def classify_intent_node(state: BrainState) -> dict[str, Any]:
    """Tag the prompt with a deterministic intent."""
    return {"intent": classify_intent(state.get("prompt", ""))}


def _steps_for(intent: Intent, prompt: str) -> list[ExecutionStep]:
    """Expand an intent into ordered ExecutionSteps (deterministic)."""
    if intent == Intent.TUTORIAL:
        return [
            ExecutionStep(
                step_id="lookup-concept",
                title="Look up canonical concept",
                tool_call=ToolCallRequest(
                    tool="lhstem_knowledge",
                    args={"operation": "search", "query": prompt},
                    safety_tier=SafetyTier.SAFE,
                    description="Query canonical LearningHubSTEM knowledge",
                ),
            ),
            ExecutionStep(
                step_id="synthesize",
                title="Synthesize a grounded explanation",
            ),
        ]
    if intent == Intent.GAME_DEV:
        return [
            ExecutionStep(
                step_id="spec-planning",
                title="Formulate Game Project Specification",
                tool_call=ToolCallRequest(
                    tool="gamedev_plan",
                    args={"prompt": prompt},
                    safety_tier=SafetyTier.SAFE,
                    description="Plan game architecture and component requirements",
                ),
            ),
            ExecutionStep(
                step_id="scaffold-generation",
                title="Scaffold Game Engine & Core Rules",
                tool_call=ToolCallRequest(
                    tool="gamedev_scaffold",
                    args={"prompt": prompt},
                    safety_tier=SafetyTier.SAFE,
                    description="Generate game project structure and pure rule contracts",
                ),
            ),
            ExecutionStep(
                step_id="architecture-validation",
                title="Validate Game Architecture & Domain Purity",
                tool_call=ToolCallRequest(
                    tool="gamedev_validate",
                    args={},
                    safety_tier=SafetyTier.SAFE,
                    description="Validate engine boundary isolation and determinism",
                ),
            ),
            ExecutionStep(
                step_id="headless-verification",
                title="Execute Headless Rule Verification in Isolated Sandbox",
                tool_call=ToolCallRequest(
                    tool="gamedev_verify",
                    args={},
                    safety_tier=SafetyTier.DESTRUCTIVE,
                    description="Execute headless game tests in isolated sandbox",
                ),
            ),
            ExecutionStep(
                step_id="synthesize",
                title="Synthesize Game Dev Delivery Summary",
            ),
        ]
    if intent == Intent.FILE_QUERY:
        return [ExecutionStep(step_id="access-workspace", title="Access workspace file")]
    if intent == Intent.TOOL_SEARCH:
        return [ExecutionStep(step_id="run-tool", title="Run requested tool")]
    if intent == Intent.MULTI_STEP:
        return [ExecutionStep(step_id="sequence", title="Sequence multi-step task")]
    return [ExecutionStep(step_id="respond", title="Respond directly")]


def build_plan_node(state: BrainState) -> dict[str, Any]:
    """Turn the classified intent into an ExecutionPlan."""
    intent = state.get("intent", Intent.DIRECT_CHAT)
    prompt = state.get("prompt", "")
    plan = ExecutionPlan(
        goal=prompt,
        steps=tuple(_steps_for(intent, prompt)),
        status=PlanStatus.IN_PROGRESS,
    )
    return {"plan": plan}


async def synthesize_node(state: BrainState, router: ModelRouter) -> dict[str, Any]:
    """Produce a response via the model router; record which provider served it."""
    prompt = state.get("prompt", "")
    intent = state.get("intent", Intent.DIRECT_CHAT) or Intent.DIRECT_CHAT
    messages = [
        LLMMessage(
            role="system",
            content="You are PROFESSOR-J, a general-purpose AI operating system.",
        ),
        LLMMessage(
            role="user",
            content=f"[intent={intent.value}]\n{prompt}",
        ),
    ]
    result = await router.generate(messages)
    return {"response": result.text, "provider_used": result.provider}


def _make_synthesize_node(router: ModelRouter) -> Any:
    """Return an async LangGraph node bound to the given router."""

    async def _node(state: BrainState) -> dict[str, Any]:
        return await synthesize_node(state, router)

    return _node


def build_brain_graph(router: ModelRouter | None = None) -> Any:
    """Compile the LangGraph pipeline (compiled graph is callable).

    ``router`` defaults to an isolated router backed by the deterministic
    MockProvider so the graph is safe to run anywhere.
    """
    if router is None:
        router = ModelRouter()
        router.register_provider(MockProvider(name="mock", model="mock-model"))
    graph = StateGraph(BrainState)

    graph.add_node("classify", classify_intent_node)
    graph.add_node("plan", build_plan_node)
    graph.add_node("synthesize", _make_synthesize_node(router))

    graph.add_edge(START, "classify")
    graph.add_edge("classify", "plan")
    graph.add_edge("plan", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile()


class CognitiveBrain:
    """Facade over the compiled LangGraph brain."""

    def __init__(self, router: ModelRouter | None = None) -> None:
        self.router = router or ModelRouter(ProviderCatalog([MockProvider()]))
        self.graph = build_brain_graph(self.router)
        self.intent = classify_intent

    async def run(self, prompt: str) -> dict[str, Any]:
        """Run the brain end-to-end (async) and return the final state."""
        out = await self.graph.ainvoke({"prompt": prompt})
        return {
            "intent": (out.get("intent") or Intent.DIRECT_CHAT).value,
            "response": out.get("response", ""),
            "provider": out.get("provider_used", ""),
            "plan_steps": len(out.get("plan", ExecutionPlan()).steps),
        }
