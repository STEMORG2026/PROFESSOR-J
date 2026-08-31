"""Game Development Domain Models — Pure Python dataclasses for game specifications.

Invariants:
- Pure Python 3.11+ dataclasses only.
- ZERO imports from adapters/, brain/, db/, tools/, or external game engines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from app.domain.time import utc_now


class EngineTarget(str, Enum):
    """Target game engine or execution runtime."""

    PURE_CORE = "pure_core"  # Headless, deterministic rules (C# / Python)
    UNITY = "unity"  # Unity Engine (C# / WebGL / Desktop)
    GODOT = "godot"  # Godot Engine (GDScript / C#)
    UNREAL = "unreal"  # Unreal Engine (C++ / Blueprints)
    WEB_CANVAS = "web_canvas"  # Browser HTML5 / Canvas / WebGL
    CUSTOM = "custom"  # Custom runtime / engine


class GameGenre(str, Enum):
    """Game genre classification."""

    BOARD_GAME = "board_game"
    TURN_BASED_STRATEGY = "turn_based_strategy"
    PUZZLE = "puzzle"
    ARCADE = "arcade"
    RPG = "rpg"
    CARD_GAME = "card_game"
    SIMULATION = "simulation"
    EDUCATIONAL_STEM = "educational_stem"


class GameArchitecturePattern(str, Enum):
    """Architectural pattern governing game codebase organization."""

    PURE_CORE_HEADLESS = "pure_core_headless"  # Pure rules + presentation separation
    ECS = "ecs"  # Entity Component System
    STATE_MACHINE_EVENT_DRIVEN = "state_machine_event_driven"  # Event bus + hierarchical FSM
    MODEL_VIEW_PRESENTER = "model_view_presenter"  # MVP separation


class GameSystemCategory(str, Enum):
    """Taxonomy of game component and subsystem domains."""

    CORE = "core"
    STATE = "state"
    GAMEPLAY = "gameplay"
    SPATIAL = "spatial"
    AI = "ai"
    SIMULATION = "simulation"
    CARD = "card"
    PRESENTATION = "presentation"


class GameSystemType(str, Enum):
    """Standard game subsystems."""

    RULES_ENGINE = "rules_engine"
    TURN_MANAGER = "turn_manager"
    GRID_BOARD = "grid_board"
    DICE_RNG = "dice_rng"
    INVENTORY = "inventory"
    COMBAT = "combat"
    MOVEMENT = "movement"
    SCORING = "scoring"
    SAVE_STATE = "save_state"
    EVENT_BUS = "event_bus"
    AI_DECISION = "ai_decision"
    STATE_MACHINE = "state_machine"
    DECK_MANAGER = "deck_manager"
    FIXED_TIMESTEP = "fixed_timestep"
    SPATIAL_INDEX_2D = "spatial_index_2d"
    COMMAND_DISPATCHER = "command_dispatcher"


class ModificationScope(str, Enum):
    """Classification of code modification targets for autonomous repair safety."""

    IMPLEMENTATION = "implementation"  # Safe to modify during repair
    TEST = "test"  # REJECTED: Tests are immutable specifications
    CONFIGURATION = "configuration"  # REJECTED: Build/project configs
    GOVERNANCE = "governance"  # REJECTED: Governance, AGENTS.md, charters
    FRAMEWORK = "framework"  # REJECTED: PROFESSOR-J platform code
    DEPENDENCY = "dependency"  # REJECTED: Third-party dependencies


class MigrationSemantics(str, Enum):
    """Semantics of game state schema transitions."""

    ADDITIVE = "additive"  # New fields with defaults; 100% forward compatible
    DESTRUCTIVE = "destructive"  # Removed fields; old data dropped
    LOSSY = "lossy"  # Reverse v2 -> v1 drops v2-specific fields
    REVERSIBLE = "reversible"  # Bijective mapping preserving full round-trip
    INCOMPATIBLE = "incompatible"  # Type conflict requiring explicit conversion


class GameWorkflowType(str, Enum):
    """Goal-driven game development workflow lifecycles."""

    CREATE_GAME = "create_game"
    ADD_FEATURE = "add_feature"
    FIX_BUG = "fix_bug"
    REFACTOR_SYSTEM = "refactor_system"
    TEST_AND_REPAIR = "test_and_repair"
    OPTIMIZE = "optimize"


class GameKnowledgeCategory(str, Enum):
    """Taxonomy of game engineering knowledge domains."""

    ARCHITECTURE = "architecture"
    STATE_MANAGEMENT = "state_management"
    GAMEPLAY_SYSTEMS = "gameplay_systems"
    AI_AND_DECISION = "ai_and_decision"
    PHYSICS_AND_COLLISION = "physics_and_collision"
    INPUT_AND_CONTROL = "input_and_control"
    STORAGE_AND_STATE = "storage_and_state"
    TESTING_AND_REPAIR = "testing_and_repair"


@dataclass(frozen=True, slots=True)
class GameProjectModel:
    """Structural model of an analyzed game project workspace."""

    project_name: str
    root_dir: str
    architecture_pattern: GameArchitecturePattern = GameArchitecturePattern.PURE_CORE_HEADLESS
    detected_systems: tuple[str, ...] = field(default_factory=tuple)
    state_models: tuple[str, ...] = field(default_factory=tuple)
    intent_handlers: tuple[str, ...] = field(default_factory=tuple)
    events_emitted: tuple[str, ...] = field(default_factory=tuple)
    test_files: tuple[str, ...] = field(default_factory=tuple)
    source_files: tuple[str, ...] = field(default_factory=tuple)
    schema_version: int = 1
    engine_target: EngineTarget = EngineTarget.PURE_CORE
    is_pure_core: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GameKnowledgeTopic:
    """Structured, queryable engineering knowledge topic for reasoning and code generation."""

    topic_id: str
    name: str
    category: GameKnowledgeCategory
    summary: str
    key_invariants: tuple[str, ...] = field(default_factory=tuple)
    anti_patterns: tuple[str, ...] = field(default_factory=tuple)
    recommended_patterns: tuple[GameArchitecturePattern, ...] = field(default_factory=tuple)
    testing_strategy: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class StateFieldDiff:
    """Diff describing a change to a single field in a game state schema."""

    field_name: str
    change_type: str  # "added", "removed", "renamed", "type_changed", "default_changed"
    old_type: str | None = None
    new_type: str | None = None
    default_value: Any = None
    old_name: str | None = None


@dataclass(frozen=True, slots=True)
class StateSchemaDiff:
    """Overall schema diff between two state versions."""

    from_version: int
    to_version: int
    added_fields: tuple[StateFieldDiff, ...] = field(default_factory=tuple)
    removed_fields: tuple[StateFieldDiff, ...] = field(default_factory=tuple)
    renamed_fields: tuple[StateFieldDiff, ...] = field(default_factory=tuple)
    modified_fields: tuple[StateFieldDiff, ...] = field(default_factory=tuple)
    requires_migration: bool = True


@dataclass(frozen=True, slots=True)
class StateMigrationResult:
    """Outcome of migrating a state instance from an older schema version."""

    success: bool
    from_version: int
    to_version: int
    migrated_state: dict[str, Any]
    applied_steps: tuple[str, ...] = field(default_factory=tuple)
    error: str | None = None


@dataclass(frozen=True, slots=True)
class GameRepairAudit:
    """Audit log of an autonomous repair attempt ensuring safety and specification preservation."""

    hypothesis: str
    invariant_targeted: str
    files_considered: tuple[str, ...] = field(default_factory=tuple)
    files_modified: tuple[str, ...] = field(default_factory=tuple)
    test_files_touched: bool = False
    tests_weakened: bool = False
    tests_before_count: int = 0
    tests_after_count: int = 0
    iteration_count: int = 1
    success: bool = True
    rejected_reason: str | None = None


@dataclass(frozen=True, slots=True)
class GameWorkflowPlan:
    """Structured plan for executing a game development workflow."""

    workflow_type: GameWorkflowType
    goal: str
    steps: tuple[str, ...] = field(default_factory=tuple)
    target_project: str = ""
    requested_feature: str = ""
    affected_systems: tuple[str, ...] = field(default_factory=tuple)
    affected_state: tuple[str, ...] = field(default_factory=tuple)
    extension_points: tuple[str, ...] = field(default_factory=tuple)
    required_components: tuple[GameComponentSpec, ...] = field(default_factory=tuple)
    required_knowledge: tuple[str, ...] = field(default_factory=tuple)
    expected_invariants: tuple[str, ...] = field(default_factory=tuple)
    tests_to_add: tuple[str, ...] = field(default_factory=tuple)
    migration_required: bool = False
    verification_strategy: str = ""
    applied_patterns: tuple[GameArchitecturePattern, ...] = field(default_factory=tuple)
    target_engine: EngineTarget = EngineTarget.PURE_CORE
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GameComponentSpec:
    """Specification of a reusable game component or subsystem."""

    name: str
    system_type: GameSystemType
    description: str
    category: GameSystemCategory = GameSystemCategory.CORE
    pattern: GameArchitecturePattern = GameArchitecturePattern.PURE_CORE_HEADLESS
    parameters: dict[str, Any] = field(default_factory=dict)
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    source_files: tuple[str, ...] = field(default_factory=tuple)
    test_files: tuple[str, ...] = field(default_factory=tuple)
    purpose: str = ""
    inputs: tuple[str, ...] = field(default_factory=tuple)
    outputs: tuple[str, ...] = field(default_factory=tuple)
    state_fields: tuple[str, ...] = field(default_factory=tuple)
    emitted_events: tuple[str, ...] = field(default_factory=tuple)
    invariants: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GameProjectSpec:
    """Specification for a game project."""

    title: str
    genre: GameGenre
    target_engine: EngineTarget = EngineTarget.PURE_CORE
    architecture_pattern: GameArchitecturePattern = GameArchitecturePattern.PURE_CORE_HEADLESS
    project_id: str = field(default_factory=lambda: f"game-{uuid4().hex[:8]}")
    description: str = ""
    components: tuple[GameComponentSpec, ...] = field(default_factory=tuple)
    target_language: str = "csharp"  # "csharp", "python", "typescript"
    max_players: int = 2
    is_deterministic: bool = True
    created_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def component_names(self) -> tuple[str, ...]:
        """Return all component names in this project."""
        return tuple(c.name for c in self.components)

    def has_system(self, system_type: GameSystemType) -> bool:
        """Check if project includes a specific game system."""
        return any(c.system_type == system_type for c in self.components)


@dataclass(frozen=True, slots=True)
class GameRuleViolation:
    """Architecture or domain rule violation in a game project."""

    rule_name: str
    file_path: str
    line_number: int | None = None
    message: str = ""
    severity: str = "error"  # "error", "warning"


@dataclass(frozen=True, slots=True)
class GameValidationReport:
    """Result of game architecture and domain purity validation."""

    is_valid: bool
    violations: tuple[GameRuleViolation, ...] = field(default_factory=tuple)
    warnings: tuple[GameRuleViolation, ...] = field(default_factory=tuple)
    architecture_pattern: GameArchitecturePattern = GameArchitecturePattern.PURE_CORE_HEADLESS
    engine_target: EngineTarget = EngineTarget.PURE_CORE
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def error_count(self) -> int:
        return len(self.violations)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)


@dataclass(frozen=True, slots=True)
class GameTestReport:
    """Outcome of headless game rule test execution."""

    success: bool
    exit_code: int
    passed_count: int
    failed_count: int
    duration_ms: float
    stdout: str = ""
    stderr: str = ""
    error: str | None = None
    timed_out: bool = False
    failed_tests: tuple[str, ...] = field(default_factory=tuple)
    failure_details: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    repair_audit: GameRepairAudit | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GameSystemSpec:
    """Detailed structural specification for a synthesized novel game subsystem."""

    system_name: str
    purpose: str
    category: GameSystemCategory = GameSystemCategory.GAMEPLAY
    state_fields: dict[str, str] = field(default_factory=dict)  # field_name -> type_str
    state_defaults: dict[str, Any] = field(default_factory=dict)
    intents: tuple[str, ...] = field(default_factory=tuple)
    intent_parameters: dict[str, dict[str, str]] = field(default_factory=dict)
    events: tuple[str, ...] = field(default_factory=tuple)
    event_payloads: dict[str, dict[str, str]] = field(default_factory=dict)
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    invariants: tuple[str, ...] = field(default_factory=tuple)
    public_operations: tuple[str, ...] = field(default_factory=tuple)
    source_files: tuple[str, ...] = field(default_factory=tuple)
    test_files: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExecutionTrace:
    """Deterministic step trace of a GameCore execution tick/intent."""

    trace_id: str
    seed: int
    tick: int
    intent_name: str
    intent_payload: dict[str, Any] = field(default_factory=dict)
    pre_state_hash: str = ""
    post_state_hash: str = ""
    events_emitted: tuple[str, ...] = field(default_factory=tuple)
    success: bool = True
    error: str | None = None


@dataclass(frozen=True, slots=True)
class StateSnapshot:
    """Immutable state snapshot at a specific execution tick."""

    snapshot_id: str
    tick: int
    schema_version: int
    state_data: dict[str, Any] = field(default_factory=dict)
    state_hash: str = ""


@dataclass(frozen=True, slots=True)
class StateDelta:
    """Delta difference between two execution state snapshots."""

    from_tick: int
    to_tick: int
    changed_fields: dict[str, Any] = field(default_factory=dict)
    added_fields: dict[str, Any] = field(default_factory=dict)
    removed_fields: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class FileEdit:
    """A single atomic file modification instruction."""

    file_path: str
    target_snippet: str
    replacement_snippet: str


@dataclass(frozen=True, slots=True)
class RepairProposal:
    """Structured proposal generated by cognitive reasoning to resolve a defect."""

    proposal_id: str
    diagnosis: str
    violated_invariant: str
    root_cause: str
    target_files: tuple[str, ...]
    edits: tuple[FileEdit, ...]
    rationale: str
    confidence: float = 1.0
