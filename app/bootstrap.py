"""Composition root — wires the app's singletons together (Phase 4/9).

Assembles the observable subsystems (session, memory, reflexion, db, tools,
knowledge, brain) off :class:`~app.config.settings.Settings` so the rest of the
code depends on constructed services, not on global state. This is the single
place to see what a running professor instance holds.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.db import MasteryRepository, SqliteDatabaseEngine, TranscriptRepository
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
    workspace: WorkspaceManager
    tools: ToolExecutor
    knowledge: LHSKnowledgeAdapter | None
    research: ResearchAgent
    policy: SafetyPolicy

    def health(self) -> dict[str, object]:
        """Return per-subsystem liveness for a health/status endpoint (Phase 9b)."""
        return {
            "db": self.db is not None,
            "sessions": self.sessions is not None,
            "memory": self.memory is not None,
            "tools": self.tools is not None,
            "knowledge": self.knowledge is not None,
            "research": self.research is not None,
            "ready": all(
                (
                    self.db is not None,
                    self.sessions is not None,
                    self.memory is not None,
                    self.tools is not None,
                )
            ),
        }


def build_root(
    *,
    db_path: str = "data/professor.db",
    lhs_export: str = "LearningHubSTEM/exports/knowledge.json",
    workspace_root: str = "data/workspace",
) -> AppRoot:
    """Build and wire the application singletons (SQLite/in-memory defaults)."""
    db = SqliteDatabaseEngine(db_path)
    db.create_schema()

    memory_backend = InMemoryBackend()
    memory = MemoryService(memory_backend)
    reflexion = ReflexionEngine(memory_backend)
    research = ResearchAgent(InMemoryBackend())

    # LHS is optional: load if the export file is present, else degrade to no
    # canonical knowledge (the brain still runs on the model pool).
    knowledge: LHSKnowledgeAdapter | None = None
    try:
        knowledge = LHSKnowledgeAdapter(lhs_export)
    except Exception as exc:  # noqa: BLE001 - export absent/invalid; degrade gracefully
        logger.warning("LHS export unavailable (%s); running without canonical knowledge", exc)

    workspace = WorkspaceManager(workspace_root)
    policy = SafetyPolicy(approval_callback=None)
    tools = ToolExecutor(policy)
    tools.register_sandbox_tools()

    return AppRoot(
        sessions=SessionManager(),
        memory=memory,
        reflexion=reflexion,
        db=db,
        mastery=MasteryRepository(db),
        transcripts=TranscriptRepository(db),
        workspace=workspace,
        tools=tools,
        knowledge=knowledge,
        research=research,
        policy=policy,
    )


__all__ = ["build_root", "AppRoot"]
