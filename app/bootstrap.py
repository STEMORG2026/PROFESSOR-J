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

from app.authority.gateway import AuthorityGateway, set_gateway
from app.authority.principal import Principal
from app.db import MasteryRepository, SessionRepository, SqliteDatabaseEngine, TranscriptRepository
from app.authority.policy import default_register_policy
from app.db import MasteryRepository, SqliteDatabaseEngine, TranscriptRepository
from app.gamedev import GameDevAgent
from app.guardrails.policy import SafetyPolicy
from app.knowledge import ResearchAgent
from app.knowledge.lhs_adapter import LHSKnowledgeAdapter
from app.memory import InMemoryBackend, MemoryService, ReflexionEngine
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
    lhs_export: str = "LearningHubSTEM/exports/knowledge.json",
    workspace_root: str = "data/workspace",
) -> AppRoot:
    """Build and wire the application singletons (SQLite/in-memory defaults).

    The composition root creates Principals for each agent type and wires them
    into the AuthorityGateway. Agents receive their Principal as a capability;
    they cannot create Principals themselves.
    """
    db = SqliteDatabaseEngine(db_path)
    db.create_schema()

    memory_backend = InMemoryBackend()
    memory = MemoryService(memory_backend)
    reflexion = ReflexionEngine(memory_backend)
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
    )


__all__ = ["build_root", "AppRoot"]
