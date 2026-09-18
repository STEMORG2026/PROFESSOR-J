"""Orchestration package — Phase 9+10 agent orchestration plane."""

from app.orchestration.agent_router import AgentRouter, TaskClassification, create_agent_router
from app.orchestration.hooks import HookEvent, HookResult, HooksSystem, create_hooks_system
from app.orchestration.plugin_registry import (
    PluginCapability,
    PluginRegistry,
    create_plugin_registry,
)
from app.orchestration.sandbox import (
    SandboxConfig,
    SandboxedExecution,
    SandboxResult,
    create_sandbox,
)
from app.orchestration.scheduler import ScheduledJob, Scheduler, create_scheduler
from app.orchestration.session_manager import SessionData, SessionManager, create_session_manager
from app.orchestration.subagent_manager import (
    SubagentManager,
    SubagentProcess,
    create_subagent_manager,
)
from app.orchestration.task_tracker import (
    Goal,
    Plan,
    TaskStatus,
    TaskTracker,
    TodoItem,
    create_task_tracker,
)
from app.orchestration.tool_search import ToolInfo, ToolSearch, create_tool_search

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
    "SessionManager",
    "SessionData",
    "create_session_manager",
    "ToolSearch",
    "ToolInfo",
    "create_tool_search",
    "SandboxedExecution",
    "SandboxConfig",
    "SandboxResult",
    "create_sandbox",
    "TaskTracker",
    "TodoItem",
    "Goal",
    "Plan",
    "TaskStatus",
    "create_task_tracker",
    "Scheduler",
    "ScheduledJob",
    "create_scheduler",
]
