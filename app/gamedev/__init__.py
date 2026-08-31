"""Game Development capability package for PROFESSOR-J."""

from app.gamedev.adapters.pure_core import PureCoreAdapter
from app.gamedev.adapters.unity import UnityEngineAdapter
from app.gamedev.agent import GameDevAgent
from app.gamedev.analyzer import GameProjectAnalyzer
from app.gamedev.base import EngineRegistry, GameEngineAdapter
from app.gamedev.certification import GameCoreCertifier
from app.gamedev.components import GameComponentCatalog
from app.gamedev.core import BaseGameCore, GameCoreProtocol
from app.gamedev.fuzzer import FuzzResult, GameCoreFuzzer
from app.gamedev.knowledge import GameKnowledgeCatalog
from app.gamedev.patterns import GamePatternCatalog, PatternDefinition
from app.gamedev.presentation import (
    FakePresentationAdapter,
    PresentationAdapterProtocol,
    PresentationBridge,
    UnityEntityView,
    UnityEventPresenter,
    UnityGameRunner,
    UnityInputAdapter,
    UnityStatePresenter,
)
from app.gamedev.primitives import (
    BoundingBox2D,
    ContinuousSpace2D,
    EntityRegistry,
    ExecutionTracer,
    FlowResource,
    Position2D,
    SeededPRNGStream,
    Velocity2D,
)
from app.gamedev.reasoner import (
    CognitiveContext,
    GameDevReasoner,
    ModelGameDevReasoner,
    RepairContext,
)
from app.gamedev.repair import (
    ASTPatchValidator,
    CognitiveRepairEngine,
    RepairCoordinator,
)
from app.gamedev.replay import DeterministicReplayer
from app.gamedev.schema import GameStateEvolutionEngine, GameStateSchema
from app.gamedev.synthesizer import SystemSynthesizer
from app.gamedev.validator import GameArchitectureValidator
from app.gamedev.workflows import GameWorkflowEngine

__all__ = [
    "GameEngineAdapter",
    "EngineRegistry",
    "PureCoreAdapter",
    "UnityEngineAdapter",
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
    "ASTPatchValidator",
    "FlowResource",
    "BoundingBox2D",
    "ContinuousSpace2D",
    "Position2D",
    "Velocity2D",
    "EntityRegistry",
    "SeededPRNGStream",
    "ExecutionTracer",
    "GameDevReasoner",
    "ModelGameDevReasoner",
    "CognitiveContext",
    "RepairContext",
    "SystemSynthesizer",
    "GameCoreProtocol",
    "BaseGameCore",
    "DeterministicReplayer",
    "GameCoreFuzzer",
    "FuzzResult",
    "GameCoreCertifier",
    "PresentationAdapterProtocol",
    "PresentationBridge",
    "FakePresentationAdapter",
    "UnityInputAdapter",
    "UnityEventPresenter",
    "UnityEntityView",
    "UnityStatePresenter",
    "UnityGameRunner",
]
