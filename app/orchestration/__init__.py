"""Orchestration package — Phase 9 agent orchestration plane."""

from app.orchestration.agent_router import AgentRouter, TaskClassification, create_agent_router
from app.orchestration.hooks import HookEvent, HookResult, HooksSystem, create_hooks_system
from app.orchestration.plugin_registry import (
    PluginCapability,
    PluginRegistry,
    create_plugin_registry,
)
from app.orchestration.subagent_manager import (
    SubagentManager,
    SubagentProcess,
    create_subagent_manager,
)

__all__ = [
    "SubagentManager",
    "SubagentProcess",
    "create_subagent_manager",
    "PluginRegistry",
    "PluginCapability",
    "create_plugin_registry",
    "AgentRouter",
    "TaskClassification",
    "create_agent_router",
    "HooksSystem",
    "HookEvent",
    "HookResult",
    "create_hooks_system",
]
