"""PROFESSOR-J Domain Layer — Pure Frozen Dataclasses.

Zero external dependencies. Zero framework imports. Serializable, validated, frozen.
"""

from app.domain.concept import ConceptEntity, ReviewStatus
from app.domain.gamedev import (
    EngineTarget,
    GameArchitecturePattern,
    GameComponentSpec,
    GameGenre,
    GameKnowledgeCategory,
    GameKnowledgeTopic,
    GameProjectModel,
    GameProjectSpec,
    GameRepairAudit,
    GameRuleViolation,
    GameSystemCategory,
    GameSystemType,
    GameTestReport,
    GameValidationReport,
    GameWorkflowPlan,
    GameWorkflowType,
    MigrationSemantics,
    ModificationScope,
    StateFieldDiff,
    StateMigrationResult,
    StateSchemaDiff,
)
from app.domain.learner import (
    Evaluation,
    LearnerState,
    MasteryScore,
    MisconceptionState,
    MisconceptionType,
    PedagogicalTurn,
    TutoringMode,
)
from app.domain.plan import (
    ExecutionPlan,
    ExecutionStep,
    PlanStatus,
    StepStatus,
    ToolCallRequest,
)
from app.domain.session import Conversation, Message, MessageRole, Provenance, Session
from app.domain.tool import ApprovalState, SafetyTier

__all__ = [
    # Concepts
    "ConceptEntity",
    "ReviewStatus",
    # GameDev
    "EngineTarget",
    "GameGenre",
    "GameArchitecturePattern",
    "GameSystemCategory",
    "GameSystemType",
    "ModificationScope",
    "MigrationSemantics",
    "GameProjectModel",
    "GameComponentSpec",
    "GameProjectSpec",
    "GameRuleViolation",
    "GameValidationReport",
    "GameTestReport",
    "GameWorkflowType",
    "GameWorkflowPlan",
    "GameKnowledgeCategory",
    "GameKnowledgeTopic",
    "StateFieldDiff",
    "StateSchemaDiff",
    "StateMigrationResult",
    "GameRepairAudit",
    # Plans
    "ExecutionPlan",
    "ExecutionStep",
    "PlanStatus",
    "StepStatus",
    "ToolCallRequest",
    # Learner
    "LearnerState",
    "MasteryScore",
    "PedagogicalTurn",
    "MisconceptionState",
    "MisconceptionType",
    "TutoringMode",
    "Evaluation",
    # Session
    "Session",
    "Conversation",
    "Message",
    "MessageRole",
    "Provenance",
    # Tools
    "SafetyTier",
    "ApprovalState",
]
