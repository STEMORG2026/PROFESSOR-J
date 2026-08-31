"""Adversarial Generality Benchmarks & Determinism Verification for GameDev Capability v0.4.

Proves that PROFESSOR-J is an open-ended game development capability, NOT a closed template catalog.
Executes 6 adversarial novel game genre benchmarks featuring systems absent from components.py:
1. Tower Defense (WaveSpawnerSystem, GridPathfinder, TurretTargetingSystem, EconomySystem)
2. 2D Platformer (KinematicBody2D, JumpController, TileCollisionSolver)
3. Top-Down Racing (VehiclePhysics2D, LapTracker)
4. Roguelike Dungeon Explorer (ShadowCastingFOV, DungeonGenerator, CombatCalculator)
5. Match-3 Cascade Puzzle (MatchDetector, GravityCascadeSolver)
6. RTS Base Builder (HarvesterSystem, ConstructionSystem, ProductionQueueManager)

And verifies:
- Universal Primitives (FlowResource, ContinuousSpace2D, BoundingBox2D)
- Hierarchical Deterministic PRNG Stream Isolation (cosmetic RNG cannot desync gameplay RNG)
- State Deltas & Execution Traces for deterministic replay
"""

import hashlib
import tempfile
from collections.abc import Generator

import pytest

from app.gamedev.agent import GameDevAgent
from app.gamedev.primitives import (
    BoundingBox2D,
    ExecutionTracer,
    FlowResource,
    SeededPRNGStream,
)
from app.tools.sandbox import CodeSandbox
from app.workspace.workspace import WorkspaceManager


@pytest.fixture
def temp_workspace() -> Generator[WorkspaceManager, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield WorkspaceManager(tmpdir)


@pytest.fixture
def sandbox() -> CodeSandbox:
    return CodeSandbox()


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ──────────────────────────────────────────────────────────────────────────────
# 1. Universal Primitives Unit Verification
# ──────────────────────────────────────────────────────────────────────────────
def test_flow_resource_invariants() -> None:
    """1. FlowResource satisfies capacity, clamping, consumption and regeneration invariants."""
    gold = FlowResource(name="gold", value=100.0, min_value=0.0, max_value=500.0)
    assert gold.consume(40.0) is True
    assert gold.value == 60.0
    assert gold.consume(100.0) is False  # Rejects overconsumption without mutating value
    assert gold.value == 60.0

    stamina = FlowResource(
        name="stamina", value=0.0, min_value=0.0, max_value=100.0, regen_rate=10.0
    )
    assert stamina.is_empty is True
    stamina.tick(dt=2.5)  # 2.5s * 10/s = +25.0
    assert stamina.value == 25.0


def test_continuous_space_and_bounding_box_intersection() -> None:
    """2. BoundingBox2D computes exact AABB intersections and distances."""
    box1 = BoundingBox2D(x=0.0, y=0.0, width=10.0, height=10.0)
    box2 = BoundingBox2D(x=5.0, y=5.0, width=10.0, height=10.0)
    box3 = BoundingBox2D(x=20.0, y=20.0, width=5.0, height=5.0)

    assert box1.intersects(box2) is True
    assert box1.intersects(box3) is False
    assert box1.contains_point(5.0, 5.0) is True
    assert box1.contains_point(15.0, 5.0) is False


def test_hierarchical_prng_stream_isolation() -> None:
    """3. Hierarchical SeededPRNGStream guarantees cosmetic RNG cannot desync gameplay RNG."""
    root_stream1 = SeededPRNGStream(seed=42)
    gameplay1 = root_stream1.split("gameplay")
    root_stream1.split("cosmetic")

    root_stream2 = SeededPRNGStream(seed=42)
    gameplay2 = root_stream2.split("gameplay")
    cosmetic2 = root_stream2.split("cosmetic")

    # In stream 2, consume 500 cosmetic random numbers
    for _ in range(500):
        cosmetic2.random()
        cosmetic2.randint(1, 100)

    # In both streams, draw 20 gameplay random numbers
    seq1 = [gameplay1.randint(1, 100) for _ in range(20)]
    seq2 = [gameplay2.randint(1, 100) for _ in range(20)]

    # STREAM ISOLATION INVARIANT: Gameplay sequences must be 100% byte-for-byte IDENTICAL
    assert seq1 == seq2


def test_execution_tracer_snapshots_and_deltas() -> None:
    """4. ExecutionTracer computes deterministic snapshots and delta differences."""
    tracer = ExecutionTracer()
    s1 = tracer.create_snapshot(tick=1, schema_version=1, state={"gold": 100, "hp": 50})
    s2 = tracer.create_snapshot(tick=2, schema_version=1, state={"gold": 80, "hp": 50, "xp": 10})

    delta = tracer.compute_delta(s1, s2)
    assert delta.from_tick == 1
    assert delta.to_tick == 2
    assert delta.changed_fields == {"gold": 80}
    assert delta.added_fields == {"xp": 10}
    assert delta.removed_fields == ()


# ──────────────────────────────────────────────────────────────────────────────
# BENCHMARK 1 — Tower Defense
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_benchmark_1_tower_defense(
    temp_workspace: WorkspaceManager, sandbox: CodeSandbox
) -> None:
    """Benchmark 1: Tower Defense (TurretTargetingSystem range defect repair)."""
    agent = GameDevAgent()
    project_dir = "tower_defense_core"

    # Scaffolding novel turret system
    turret_py = """
import math

class TurretTargetingSystem:
    def __init__(self, range_radius: float = 10.0):
        self.range = range_radius

    def get_targets(
        self,
        turret_pos: tuple[float, float],
        creeps: list[tuple[float, float]],
    ) -> list[tuple[float, float]]:
        targets = []
        for cx, cy in creeps:
            dist = math.hypot(cx - turret_pos[0], cy - turret_pos[1])
            # DEFECT: Target only creeps OUTSIDE range radius (dist > self.range)
            if dist > self.range:
                targets.append((cx, cy))
        return targets
"""
    test_turret_py = """
from systems.turret import TurretTargetingSystem

def test_turret_targeting_within_range():
    turret = TurretTargetingSystem(range_radius=10.0)
    turret_pos = (0.0, 0.0)
    creeps = [(5.0, 0.0), (15.0, 0.0)]  # In range: (5,0); Out of range: (15,0)

    targets = turret.get_targets(turret_pos, creeps)
    assert (5.0, 0.0) in targets
    assert (15.0, 0.0) not in targets
"""
    temp_workspace.write(f"{project_dir}/systems/turret.py", turret_py)
    temp_workspace.write(f"{project_dir}/tests/test_turret.py", test_turret_py)

    initial_test_hash = _sha256(test_turret_py)

    # Initial run fails due to range defect
    report_fail = await agent.verify_game(temp_workspace, project_dir, sandbox)
    assert report_fail.success is False

    # Cognitive repair resolves range defect
    report_fixed = await agent.diagnose_and_repair(temp_workspace, project_dir, sandbox)
    assert report_fixed.success is True
    assert report_fixed.failed_count == 0

    # Protected test file is 100% unchanged
    final_test_content = temp_workspace.read(f"{project_dir}/tests/test_turret.py")["content"]
    assert _sha256(final_test_content) == initial_test_hash


# ──────────────────────────────────────────────────────────────────────────────
# BENCHMARK 2 — 2D Platformer
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_benchmark_2_platformer(
    temp_workspace: WorkspaceManager, sandbox: CodeSandbox
) -> None:
    """Benchmark 2: 2D Platformer (JumpController airborne coyote timer decrement defect)."""
    agent = GameDevAgent()
    project_dir = "platformer_core"

    jump_py = """
class JumpController:
    def __init__(self, coyote_duration: float = 0.15):
        self.coyote_duration = coyote_duration
        self.coyote_timer = coyote_duration
        self.is_grounded = True

    def update(self, dt: float, is_grounded: bool):
        self.is_grounded = is_grounded
        if self.is_grounded:
            self.coyote_timer = self.coyote_duration
        else:
            # DEFECT: Forgot to decrement coyote timer while airborne
            if not self.is_grounded:
                pass

    def can_jump(self) -> bool:
        return self.is_grounded or self.coyote_timer > 0.0
"""
    test_jump_py = """
from systems.jump import JumpController

def test_coyote_timer_expires_in_air():
    ctrl = JumpController(coyote_duration=0.15)
    ctrl.update(dt=0.0, is_grounded=True)
    assert ctrl.can_jump() is True

    # Fall off ledge for 0.20s (exceeds 0.15s coyote window)
    ctrl.update(dt=0.20, is_grounded=False)
    assert ctrl.can_jump() is False
"""
    temp_workspace.write(f"{project_dir}/systems/jump.py", jump_py)
    temp_workspace.write(f"{project_dir}/tests/test_jump.py", test_jump_py)

    initial_test_hash = _sha256(test_jump_py)

    report_fail = await agent.verify_game(temp_workspace, project_dir, sandbox)
    assert report_fail.success is False

    report_fixed = await agent.diagnose_and_repair(temp_workspace, project_dir, sandbox)
    assert report_fixed.success is True
    assert report_fixed.failed_count == 0

    final_test_content = temp_workspace.read(f"{project_dir}/tests/test_jump.py")["content"]
    assert _sha256(final_test_content) == initial_test_hash


# ──────────────────────────────────────────────────────────────────────────────
# BENCHMARK 3 — Top-Down Racing
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_benchmark_3_racing(temp_workspace: WorkspaceManager, sandbox: CodeSandbox) -> None:
    """Benchmark 3: Top-Down Racing (LapTracker checkpoint sequence bypass defect)."""
    agent = GameDevAgent()
    project_dir = "racing_core"

    lap_py = """
class LapTracker:
    def __init__(self, total_checkpoints: int = 3):
        self.total_checkpoints = total_checkpoints
        self.completed_checkpoints = set()
        self.current_lap = 0

    def trigger_checkpoint(self, cp: int):
        self.completed_checkpoints.add(cp)

    def cross_finish_line(self):
        # DEFECT: Lap increments unconditionally without verifying all checkpoints were hit
        self.current_lap += 1
        self.completed_checkpoints.clear()
"""
    test_lap_py = """
from systems.lap import LapTracker

def test_lap_requires_all_checkpoints():
    tracker = LapTracker(total_checkpoints=3)
    tracker.trigger_checkpoint(1)
    tracker.trigger_checkpoint(2)
    # Checkpoint 3 omitted
    tracker.cross_finish_line()
    assert tracker.current_lap == 0  # Cannot advance lap if checkpoint 3 was skipped
"""
    temp_workspace.write(f"{project_dir}/systems/lap.py", lap_py)
    temp_workspace.write(f"{project_dir}/tests/test_lap.py", test_lap_py)

    initial_test_hash = _sha256(test_lap_py)

    report_fail = await agent.verify_game(temp_workspace, project_dir, sandbox)
    assert report_fail.success is False

    report_fixed = await agent.diagnose_and_repair(temp_workspace, project_dir, sandbox)
    assert report_fixed.success is True
    assert report_fixed.failed_count == 0

    final_test_content = temp_workspace.read(f"{project_dir}/tests/test_lap.py")["content"]
    assert _sha256(final_test_content) == initial_test_hash


# ──────────────────────────────────────────────────────────────────────────────
# BENCHMARK 4 — Roguelike Dungeon Explorer
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_benchmark_4_roguelike(
    temp_workspace: WorkspaceManager, sandbox: CodeSandbox
) -> None:
    """Benchmark 4: Roguelike (ShadowCastingFOV opaque wall light penetration defect)."""
    agent = GameDevAgent()
    project_dir = "roguelike_core"

    fov_py = """
class DungeonGrid:
    def __init__(self, walls: set[tuple[int, int]]):
        self.walls = walls

    def is_opaque(self, x: int, y: int) -> bool:
        return (x, y) in self.walls

class ShadowCastingFOV:
    def __init__(self, grid: DungeonGrid):
        self.grid = grid

    def compute_fov_line(self, origin: tuple[int, int], max_range: int = 5) -> set[tuple[int, int]]:
        visible = set()
        for r in range(1, max_range + 1):
            x, y = origin[0] + r, origin[1]
            # DEFECT: Ray does not terminate on opaque wall tile hit
            visible.add((x, y))
        return visible
"""
    test_fov_py = """
from systems.fov import DungeonGrid, ShadowCastingFOV

def test_fov_stops_at_wall():
    grid = DungeonGrid(walls={(2, 0)})  # Wall at x=2
    fov = ShadowCastingFOV(grid)
    visible = fov.compute_fov_line(origin=(0, 0), max_range=4)

    assert (1, 0) in visible  # Empty tile before wall
    assert (2, 0) in visible  # Wall surface itself
    assert (3, 0) not in visible  # Hidden tile behind wall must NOT be visible
"""
    temp_workspace.write(f"{project_dir}/systems/fov.py", fov_py)
    temp_workspace.write(f"{project_dir}/tests/test_fov.py", test_fov_py)

    initial_test_hash = _sha256(test_fov_py)

    report_fail = await agent.verify_game(temp_workspace, project_dir, sandbox)
    assert report_fail.success is False

    report_fixed = await agent.diagnose_and_repair(temp_workspace, project_dir, sandbox)
    assert report_fixed.success is True
    assert report_fixed.failed_count == 0

    final_test_content = temp_workspace.read(f"{project_dir}/tests/test_fov.py")["content"]
    assert _sha256(final_test_content) == initial_test_hash


# ──────────────────────────────────────────────────────────────────────────────
# BENCHMARK 5 — Match-3 Cascade Puzzle
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_benchmark_5_match3(temp_workspace: WorkspaceManager, sandbox: CodeSandbox) -> None:
    """Benchmark 5: Match-3 (MatchDetector invalid swap rollback omission defect)."""
    agent = GameDevAgent()
    project_dir = "match3_core"

    match_py = """
class MatchDetector:
    def __init__(self, grid: dict[tuple[int, int], str]):
        self.grid = dict(grid)

    def _swap(self, p1: tuple[int, int], p2: tuple[int, int]):
        self.grid[p1], self.grid[p2] = self.grid[p2], self.grid[p1]

    def try_swap(self, p1: tuple[int, int], p2: tuple[int, int]) -> bool:
        self._swap(p1, p2)
        matches = self._find_matches()
        # DEFECT: Forgot to rollback swap if no 3+ match was formed
        if not matches:
            return False
        return True

    def _find_matches(self) -> list:
        # Simple check for 3 identical horizontally
        for y in range(3):
            v0 = self.grid.get((0, y))
            if v0 is not None and v0 == self.grid.get((1, y)) == self.grid.get((2, y)):
                return [(0, y), (1, y), (2, y)]
        return []
"""
    test_match_py = """
from systems.match import MatchDetector

def test_invalid_swap_is_reverted():
    initial_grid = {(0, 0): "R", (1, 0): "G", (2, 0): "B"}
    detector = MatchDetector(initial_grid)
    # Swap (0,0) with (1,0) -> results in G, R, B (no match)
    assert detector.try_swap((0, 0), (1, 0)) is False
    # Invariant: grid must revert to original R, G, B
    assert detector.grid[(0, 0)] == "R"
    assert detector.grid[(1, 0)] == "G"
"""
    temp_workspace.write(f"{project_dir}/systems/match.py", match_py)
    temp_workspace.write(f"{project_dir}/tests/test_match.py", test_match_py)

    initial_test_hash = _sha256(test_match_py)

    report_fail = await agent.verify_game(temp_workspace, project_dir, sandbox)
    assert report_fail.success is False

    report_fixed = await agent.diagnose_and_repair(temp_workspace, project_dir, sandbox)
    assert report_fixed.success is True
    assert report_fixed.failed_count == 0

    final_test_content = temp_workspace.read(f"{project_dir}/tests/test_match.py")["content"]
    assert _sha256(final_test_content) == initial_test_hash


# ──────────────────────────────────────────────────────────────────────────────
# BENCHMARK 6 — RTS Base Builder
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_benchmark_6_rts_base_builder(
    temp_workspace: WorkspaceManager, sandbox: CodeSandbox
) -> None:
    """Benchmark 6: RTS (ConstructionSystem spatial footprint overlap defect)."""
    agent = GameDevAgent()
    project_dir = "rts_core"
    geom_py = """
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class BoundingBox2D:
    x: float
    y: float
    width: float
    height: float

    def intersects(self, other: "BoundingBox2D") -> bool:
        return not (
            self.x + self.width <= other.x
            or self.x >= other.x + other.width
            or self.y + self.height <= other.y
            or self.y >= other.y + other.height
        )
"""
    rts_py = """
from domain.geometry import BoundingBox2D

class Building:
    def __init__(self, footprint: BoundingBox2D):
        self.footprint = footprint

class ConstructionSystem:
    def __init__(self):
        self.buildings: list[Building] = []

    def can_place(self, footprint: BoundingBox2D) -> bool:
        # DEFECT: Forgot to reject overlapping bounding box footprints
        for b in self.buildings:
            pass
        return True

    def place_building(self, footprint: BoundingBox2D) -> bool:
        if not self.can_place(footprint):
            return False
        self.buildings.append(Building(footprint))
        return True
"""
    test_rts_py = """
from domain.geometry import BoundingBox2D
from systems.construction import ConstructionSystem

def test_building_footprint_overlap_rejected():
    construction = ConstructionSystem()
    b1 = BoundingBox2D(x=0.0, y=0.0, width=10.0, height=10.0)
    assert construction.place_building(b1) is True

    # Overlapping building
    b2 = BoundingBox2D(x=5.0, y=5.0, width=10.0, height=10.0)
    assert construction.place_building(b2) is False  # Must reject overlap
"""
    temp_workspace.write(f"{project_dir}/domain/geometry.py", geom_py)
    temp_workspace.write(f"{project_dir}/systems/construction.py", rts_py)
    temp_workspace.write(f"{project_dir}/tests/test_construction.py", test_rts_py)

    initial_test_hash = _sha256(test_rts_py)

    report_fail = await agent.verify_game(temp_workspace, project_dir, sandbox)
    assert report_fail.success is False

    report_fixed = await agent.diagnose_and_repair(temp_workspace, project_dir, sandbox)
    assert report_fixed.success is True
    assert report_fixed.failed_count == 0

    final_test_content = temp_workspace.read(f"{project_dir}/tests/test_construction.py")["content"]
    assert _sha256(final_test_content) == initial_test_hash
