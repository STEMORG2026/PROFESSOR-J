"""Game Development capability package for PROFESSOR-J."""

from app.gamedev.adapters.pure_core import PureCoreAdapter
from app.gamedev.agent import GameDevAgent
from app.gamedev.analyzer import GameProjectAnalyzer
from app.gamedev.base import EngineRegistry, GameEngineAdapter
from app.gamedev.components import GameComponentCatalog
from app.gamedev.knowledge import GameKnowledgeCatalog
from app.gamedev.patterns import GamePatternCatalog, PatternDefinition
from app.gamedev.primitives import (
    BoundingBox2D,
    ContinuousSpace2D,
    ExecutionTracer,
    FlowResource,
    SeededPRNGStream,
)
from app.gamedev.reasoner import (
    CognitiveContext,
    GameDevReasoner,
    ModelGameDevReasoner,
    RepairContext,
)
from app.gamedev.repair import CognitiveRepairEngine, RepairCoordinator
from app.gamedev.schema import GameStateEvolutionEngine, GameStateSchema
from app.gamedev.synthesizer import SystemSynthesizer
from app.gamedev.validator import GameArchitectureValidator
from app.gamedev.workflows import GameWorkflowEngine

__all__ = [
    "GameEngineAdapter",
    "EngineRegistry",
    "PureCoreAdapter",
    "GameDevAgent",
    "GameProjectAnalyzer",
    "GamePatternCatalog",
    "PatternDefinition",
    "GameComponentCatalog",
    "GameArchitectureValidator",
    "GameKnowledgeCatalog",
    "GameWorkflowEngine",
    "GameStateSchema",
    "GameStateEvolutionEngine",
    "CognitiveRepairEngine",
    "RepairCoordinator",
    "FlowResource",
    "BoundingBox2D",
    "ContinuousSpace2D",
    "SeededPRNGStream",
    "ExecutionTracer",
    "GameDevReasoner",
    "ModelGameDevReasoner",
    "CognitiveContext",
    "RepairContext",
    "SystemSynthesizer",
]
