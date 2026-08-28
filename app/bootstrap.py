"""Composition root — wires the app's singletons together (Phase 4/9).

Assembles the observable subsystems (session, memory, reflexion, db, tools,
knowledge, brain) off :class:`~app.config.settings.Settings` so the rest of the
code depends on constructed services, not on global state. This is the single
place to see what a running professor instance holds.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.db import MasteryRepository, SqliteDatabaseEngine, TranscriptRepository
from app.guardrails.policy import SafetyPolicy
from app.knowledge import ResearchAgent
from app.knowledge.lhs_adapter import LHSKnowledgeAdapter
from app.memory import InMemoryBackend, MemoryService, ReflexionEngine
from app.session import SessionManager
from app.tools import ToolExecutor
from app.workspace import WorkspaceManager


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
    knowledge: LHSKnowledgeAdapter
    research: ResearchAgent
    policy: SafetyPolicy


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

    knowledge = LHSKnowledgeAdapter(lhs_export)
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
