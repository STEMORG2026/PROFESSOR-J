"""Composition root — wires the app's singletons together (Phase 4/9).

Assembles the observable subsystems (session, memory, reflexion, db, tools,
knowledge, brain) off :class:`~app.config.settings.Settings` so the rest of the
code depends on constructed services, not on global state. This is the single
place to see what a running professor instance holds.

The composition root is the TRUST ROOT for Principal creation. It creates
Principals at agent construction time and passes them as capabilities. Agents
cannot create Principals; they only receive them as capabilities.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.authority.gateway import AuthorityGateway, set_gateway
from app.authority.policy import default_register_policy
from app.authority.principal import Principal
from app.context import ContextWindowManager
from app.db import MasteryRepository, SessionRepository, SqliteDatabaseEngine, TranscriptRepository
from app.domain.tool import SafetyTier
from app.events import InMemoryAsyncBus
from app.gamedev import GameDevAgent
from app.guardrails.policy import SafetyPolicy
from app.knowledge import ResearchAgent
from app.knowledge.lhs_adapter import LHSKnowledgeAdapter
from app.mcp.manager import MCPServerManager
from app.memory import InMemoryBackend, MemoryManager, MemoryService, ReflexionEngine
from app.prompt import PromptLoader
from app.session import SessionManager
from app.tools import ToolExecutor
from app.workspace import WorkspaceManager

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AppRoot:
    """The constructed application graph."""

    sessions: SessionManager
    memory: MemoryService
    reflexion: ReflexionEngine
    db: SqliteDatabaseEngine
    mastery: MasteryRepository
    transcripts: TranscriptRepository
    session_repo: SessionRepository
    workspace: WorkspaceManager
    tools: ToolExecutor
    knowledge: LHSKnowledgeAdapter | None
    research: ResearchAgent
    gamedev: GameDevAgent
    policy: SafetyPolicy
    gateway: AuthorityGateway
    event_bus: InMemoryAsyncBus
    context_window: ContextWindowManager
    prompt_loader: PromptLoader
    mcp: MCPServerManager
    # Phase 9: Orchestration plane
    acp_server: Any = None
    subagent_manager: Any = None
    plugin_registry: Any = None
    agent_router: Any = None
    hooks_system: Any = None
    # Phase 10: Advanced orchestration
    session_manager: Any = None
    tool_search: Any = None
    sandbox: Any = None
    task_tracker: Any = None
    scheduler: Any = None
    # Phase 11: SOTA tools
    web: Any = None
    browser: Any = None
    computer_use: Any = None

    def health(self) -> dict[str, object]:
        """Return per-subsystem liveness for a health/status endpoint (Phase 9b)."""
        return {
            "db": self.db is not None,
            "sessions": self.sessions is not None,
            "memory": self.memory is not None,
            "tools": self.tools is not None,
            "knowledge": self.knowledge is not None,
            "research": self.research is not None,
            "gamedev": self.gamedev is not None,
            "ready": all(
                (
                    self.db is not None,
                    self.sessions is not None,
                    self.memory is not None,
                    self.tools is not None,
                    self.gamedev is not None,
                )
            ),
        }


def build_root(
    *,
    db_path: str = "data/professor.db",
    lhs_export: str = "STEMMA/exports/knowledge.json",
    workspace_root: str = "data/workspace",
) -> AppRoot:
    """Build and wire the application singletons (SQLite/in-memory defaults).

    The composition root creates Principals for each agent type and wires them
    into the AuthorityGateway. Agents receive their Principal as a capability;
    they cannot create Principals themselves.
    """
    db = SqliteDatabaseEngine(db_path)
    db.create_schema()

    memory_manager = MemoryManager()
    memory = MemoryService(memory_manager)
    reflexion = ReflexionEngine(memory_manager)
    research = ResearchAgent(InMemoryBackend())
    gamedev = GameDevAgent()

    # LHS is optional: load if the export file is present, else degrade to no
    # canonical knowledge (the brain still runs on the model pool).
    knowledge: LHSKnowledgeAdapter | None = None
    try:
        knowledge = LHSKnowledgeAdapter(lhs_export)
    except Exception as exc:  # noqa: BLE001 - export absent/invalid; degrade gracefully
        logger.warning("LHS export unavailable (%s); running without canonical knowledge", exc)

    workspace = WorkspaceManager(workspace_root)
    policy = SafetyPolicy(approval_callback=None)
    # Phase 2: the composition root is the BLESSED registrar — it may provision the standard
    # toolset (incl. DESTRUCTIVE sandbox tools). Any later, non-blessed registration (agent or
    # skill self-registration) is denied by the default registration policy.
    tools = ToolExecutor(
        policy,
        register_policy=default_register_policy,
        blessed_registrar=True,
    )
    tools.register_sandbox_tools()
    tools.register_gamedev_tools(gamedev, workspace)
    tools.register_chart_tools()

    session_repo = SessionRepository(db)

    # Create the AuthorityGateway — the single authoritative execution boundary
    gateway = AuthorityGateway(
        tool_executor=tools,
        safety_policy=policy,
        allocation_path="authority/allocation.yaml",
        permission_manifest_path="authority/permission-manifest.yaml",
        audit_log_path="data/ledger/gateway_audit.jsonl",
    )
    set_gateway(gateway)

    # COMPOSITION ROOT: Create Principals for each agent type.
    # These are the ONLY places Principals are created (trust root).
    # Agents receive their Principal as a capability; they cannot create Principals.
    _researcher_principal = Principal.create(
        id="researcher",
        tier=SafetyTier.SENSITIVE,
        project="PROFESSOR-J",
        allocation_ref="PROFESSOR-J",
    )
    _architect_principal = Principal.create(
        id="architect",
        tier=SafetyTier.SENSITIVE,
        project="PROFESSOR-J",
        allocation_ref="PROFESSOR-J",
    )
    _implementer_principal = Principal.create(
        id="implementer",
        tier=SafetyTier.SENSITIVE,
        project="PROFESSOR-J",
        allocation_ref="PROFESSOR-J",
    )
    _tester_principal = Principal.create(
        id="tester",
        tier=SafetyTier.SAFE,
        project="PROFESSOR-J",
        allocation_ref="PROFESSOR-J",
    )
    _security_reviewer_principal = Principal.create(
        id="security-reviewer",
        tier=SafetyTier.SENSITIVE,
        project="PROFESSOR-J",
        allocation_ref="PROFESSOR-J",
    )
    _code_reviewer_principal = Principal.create(
        id="code-reviewer",
        tier=SafetyTier.SAFE,
        project="PROFESSOR-J",
        allocation_ref="PROFESSOR-J",
    )
    _docs_reviewer_principal = Principal.create(
        id="docs-reviewer",
        tier=SafetyTier.SAFE,
        project="PROFESSOR-J",
        allocation_ref="PROFESSOR-J",
    )
    _ci_reviewer_principal = Principal.create(
        id="ci-reviewer",
        tier=SafetyTier.SAFE,
        project="PROFESSOR-J",
        allocation_ref="PROFESSOR-J",
    )

    session_repo = SessionRepository(db)

    event_bus = InMemoryAsyncBus()
    # Passive telemetry + utilities (JARVIS parity); wired in so future call sites
    # can publish events / trim context / load externalized prompts.
    context_window = ContextWindowManager()
    prompt_loader = PromptLoader()

    # Phase 4: MCP management layer (current app.mcp.manager). Dormant by default
    # (no servers registered) but available via 'mcp' for server registration + tool
    # execution; every call is gated by the same policy as other tools.
    mcp = MCPServerManager(policy=policy)

    # Phase 9+10: Orchestration plane singletons
    from app.acp import create_acp_server
    from app.orchestration import (
        create_agent_router,
        create_hooks_system,
        create_plugin_registry,
        create_sandbox,
        create_scheduler,
        create_session_manager,
        create_subagent_manager,
        create_task_tracker,
        create_tool_search,
    )

    acp_server = create_acp_server()
    subagent_manager = create_subagent_manager()
    plugin_registry = create_plugin_registry()
    agent_router = create_agent_router()
    hooks_system = create_hooks_system()
    session_manager = create_session_manager()
    tool_search = create_tool_search()
    sandbox = create_sandbox()
    task_tracker = create_task_tracker()
    scheduler = create_scheduler()
    # Phase 11: SOTA tools
    from app.tools.browser import create_browser
    from app.tools.computer_use import create_computer_use
    from app.tools.web import create_web_search

    web = create_web_search()
    browser = create_browser()
    computer_use = create_computer_use()

    return AppRoot(
        sessions=SessionManager(),
        memory=memory,
        reflexion=reflexion,
        db=db,
        mastery=MasteryRepository(db),
        transcripts=TranscriptRepository(db),
        session_repo=session_repo,
        workspace=workspace,
        tools=tools,
        knowledge=knowledge,
        research=research,
        gamedev=gamedev,
        policy=policy,
        gateway=gateway,
        event_bus=event_bus,
        context_window=context_window,
        prompt_loader=prompt_loader,
        mcp=mcp,
        acp_server=acp_server,
        subagent_manager=subagent_manager,
        plugin_registry=plugin_registry,
        agent_router=agent_router,
        hooks_system=hooks_system,
        session_manager=session_manager,
        tool_search=tool_search,
        sandbox=sandbox,
        task_tracker=task_tracker,
        scheduler=scheduler,
        web=web,
        browser=browser,
        computer_use=computer_use,
    )


__all__ = ["build_root", "AppRoot"]
