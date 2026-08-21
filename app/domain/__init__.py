"""PROFESSOR-J Domain Layer — Pure Frozen Dataclasses.

Zero external dependencies. Zero framework imports. Serializable, validated, frozen.
"""

from app.domain.concept import ConceptEntity, ReviewStatus
from app.domain.plan import ExecutionPlan, ExecutionStep, PlanStatus, StepStatus, ToolCallRequest
from app.domain.learner import LearnerState, MasteryScore, PedagogicalTurn, MisconceptionState, MisconceptionType, TutoringMode, Evaluation
from app.domain.session import Session, Conversation, Message, MessageRole, Provenance
from app.domain.tool import SafetyTier, ApprovalState

__all__ = [
    # Concepts
    "ConceptEntity",
    "ReviewStatus",
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
