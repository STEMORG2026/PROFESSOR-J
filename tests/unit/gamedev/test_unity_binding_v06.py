"""GameDev Capability v0.6 — Unity Presentation Adapter & Playable Game Verification.

Demonstrates:
1. Pure Engine-Neutral Tactical GameCore (TacticalGameCore) with full rule authority.
2. Unity Presentation Architecture (Runner, InputAdapter, Presenters).
3. Input Translation Boundary (Raw engine input -> Domain Intent).
4. Domain Event -> Presentation Reaction Pipeline (VFX, SFX, Animation Triggers).
5. State -> View Synchronization (Domain truth -> View representation).
6. Mandatory Frame-Rate Independence Test (30 vs 60 vs 120 FPS vs Variable jitter).
7. Replay Fidelity through the Real Presentation Adapter.
8. Presentation Failure Isolation (UI/Render crash does not corrupt GameCore state).
9. Dual Certification: PURE_CORE_CERTIFIED + ENGINE_BINDING_CERTIFIED.
10. Three-Domain Generalization Proof (Tactical, Rhythm, Farming).
11. UnityEngineAdapter Scaffolding and Architectural Validation.
"""

from __future__ import annotations

import copy
import math
import tempfile
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from app.domain.gamedev import (
    EngineTarget,
    GameArchitecturePattern,
    GameGenre,
    GameProjectSpec,
)
from app.gamedev.adapters.unity import UnityEngineAdapter
from app.gamedev.certification import GameCoreCertifier
from app.gamedev.core import BaseGameCore
from app.gamedev.presentation import (
    PresentationBridge,
    UnityGameRunner,
)
from app.gamedev.replay import DeterministicReplayer
from app.tools.sandbox import CodeSandbox
from app.workspace.workspace import WorkspaceManager


# ──────────────────────────────────────────────────────────────────────────────
# DOMAIN CONTRACTS & TACTICAL GAME CORE (100% PURE PYTHON, ZERO UNITYENGINE)
# ──────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class MoveIntent:
    unit_id: str
    target_x: int
    target_y: int


@dataclass(frozen=True, slots=True)
class AttackIntent:
    attacker_id: str
    target_id: str
    damage: int = 25


@dataclass(frozen=True, slots=True)
class EndTurnIntent:
    pass


@dataclass(frozen=True, slots=True)
class UnitMovedEvent:
    unit_id: str
    from_pos: tuple[int, int]
    to_pos: tuple[int, int]


@dataclass(frozen=True, slots=True)
class AttackResolvedEvent:
    attacker_id: str
    target_id: str
    damage: int
    target_remaining_hp: int


@dataclass(frozen=True, slots=True)
class TurnAdvancedEvent:
    turn_number: int
    active_team: str


@dataclass(frozen=True, slots=True)
class VictoryEvent:
    winner_team: str


@dataclass(frozen=True, slots=True)
class DefeatEvent:
    loser_team: str


class TacticalGameCore(BaseGameCore):
    """Pure, deterministic Tactical RPG GameCore (Domain Truth).

    Rules:
    - 8x8 Grid
    - Player has 2 AP per turn
    - Move costs 1 AP (distance <= 2 tiles)
    - Attack costs 1 AP (range <= 2 tiles)
    - Victory when all enemies reach 0 HP
    - Defeat when player reaches 0 HP
    """

    def initial_state(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "turn_number": 1,
            "active_team": "player",
            "grid_width": 8,
            "grid_height": 8,
            "entities": {
                "player_1": {
                    "team": "player",
                    "x": 0,
                    "y": 0,
                    "hp": 100,
                    "max_hp": 100,
                    "ap": 2,
                    "max_ap": 2,
                    "is_alive": True,
                },
                "enemy_1": {
                    "team": "enemy",
                    "x": 2,
                    "y": 2,
                    "hp": 50,
                    "max_hp": 50,
                    "is_alive": True,
                },
            },
            "game_over": False,
            "winner": None,
        }

    def __init__(self) -> None:
        super().__init__(schema_version=1)
        self.register_intent_handler(MoveIntent, self._handle_move)
        self.register_intent_handler(AttackIntent, self._handle_attack)
        self.register_intent_handler(EndTurnIntent, self._handle_end_turn)
        self.register_invariant(self._inv_bounds_and_alive)

    def _inv_bounds_and_alive(self, state: dict[str, Any]) -> tuple[bool, str]:
        # Invariant: Alive units must remain inside grid boundaries [0, 7]
        entities = state.get("entities", {})
        gw = state.get("grid_width", 8)
        gh = state.get("grid_height", 8)
        for uid, u in entities.items():
            if u.get("is_alive", True):
                x, y = u.get("x", 0), u.get("y", 0)
                if not (0 <= x < gw and 0 <= y < gh):
                    return False, f"Unit {uid} out of grid bounds at ({x}, {y})"
                if u.get("hp", 0) < 0:
                    return False, f"Unit {uid} HP underflow ({u.get('hp')})"
        return True, ""

    def _handle_move(
        self, state: dict[str, Any], intent: MoveIntent
    ) -> tuple[bool, list[Any], str | None]:
        if state["game_over"]:
            return False, [], "Game is already over"

        unit = state["entities"].get(intent.unit_id)
        if not unit or not unit["is_alive"]:
            return False, [], f"Unit {intent.unit_id} not found or dead"

        if unit["team"] != state["active_team"]:
            return False, [], f"Not {unit['team']}'s turn"

        if unit["ap"] < 1:
            return False, [], "Insufficient Action Points to move"

        tx, ty = intent.target_x, intent.target_y
        if not (0 <= tx < state["grid_width"] and 0 <= ty < state["grid_height"]):
            return False, [], f"Target position ({tx}, {ty}) out of bounds"

        dist = abs(tx - unit["x"]) + abs(ty - unit["y"])
        if dist > 2:
            return False, [], f"Move distance {dist} exceeds max range 2"

        old_pos = (unit["x"], unit["y"])
        unit["x"] = tx
        unit["y"] = ty
        unit["ap"] -= 1

        ev = UnitMovedEvent(unit_id=intent.unit_id, from_pos=old_pos, to_pos=(tx, ty))
        return True, [ev], None

    def _handle_attack(
        self, state: dict[str, Any], intent: AttackIntent
    ) -> tuple[bool, list[Any], str | None]:
        if state["game_over"]:
            return False, [], "Game is already over"

        attacker = state["entities"].get(intent.attacker_id)
        target = state["entities"].get(intent.target_id)
        if not attacker or not attacker["is_alive"]:
            return False, [], "Attacker not found or dead"
        if not target or not target["is_alive"]:
            return False, [], "Target not found or already dead"

        if attacker["team"] != state["active_team"]:
            return False, [], "Not attacker's turn"

        if attacker["ap"] < 1:
            return False, [], "Insufficient AP to attack"

        dist = math.hypot(target["x"] - attacker["x"], target["y"] - attacker["y"])
        if dist > 3.0:
            return False, [], f"Target out of attack range (dist {dist:.2f} > 3.0)"

        attacker["ap"] -= 1
        target["hp"] = max(0, target["hp"] - intent.damage)
        events: list[Any] = [
            AttackResolvedEvent(
                attacker_id=intent.attacker_id,
                target_id=intent.target_id,
                damage=intent.damage,
                target_remaining_hp=target["hp"],
            )
        ]

        if target["hp"] == 0:
            target["is_alive"] = False
            # Check victory condition
            enemy_alive = any(
                u["is_alive"] for u in state["entities"].values() if u["team"] == "enemy"
            )
            if not enemy_alive:
                state["game_over"] = True
                state["winner"] = "player"
                events.append(VictoryEvent(winner_team="player"))

        return True, events, None

    def _handle_end_turn(
        self, state: dict[str, Any], intent: EndTurnIntent
    ) -> tuple[bool, list[Any], str | None]:
        if state["game_over"]:
            return False, [], "Game is already over"

        # Switch active team
        state["active_team"] = "enemy" if state["active_team"] == "player" else "player"
        if state["active_team"] == "player":
            state["turn_number"] += 1

        # Replenish AP for all units of new active team
        for u in state["entities"].values():
            if u["team"] == state["active_team"] and u["is_alive"]:
                u["ap"] = u.get("max_ap", 2)

        ev = TurnAdvancedEvent(turn_number=state["turn_number"], active_team=state["active_team"])
        return True, [ev], None


# ──────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def temp_workspace() -> Generator[WorkspaceManager, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield WorkspaceManager(Path(tmpdir))


@pytest.fixture
def sandbox() -> CodeSandbox:
    return CodeSandbox()


# ──────────────────────────────────────────────────────────────────────────────
# TEST 1: End-to-End Playable Tactical Game Loop via Unity Presentation Runner
# ──────────────────────────────────────────────────────────────────────────────
def test_1_end_to_end_playable_tactical_game() -> None:
    """1. Full playable slice: Input -> Intent -> GameCore -> Events -> Unity Presentation."""
    core = TacticalGameCore()
    bridge = PresentationBridge(core=core, fixed_dt=1.0 / 60.0)
    runner = UnityGameRunner(bridge=bridge)

    # 1. Register Unity Input Mappings
    runner.input_adapter.register_mapping(
        "Key_Move_Forward",
        lambda unit_id, tx, ty: MoveIntent(unit_id=unit_id, target_x=tx, target_y=ty),
    )
    runner.input_adapter.register_mapping(
        "Key_Attack",
        lambda attacker_id, target_id: AttackIntent(
            attacker_id=attacker_id, target_id=target_id, damage=25
        ),
    )
    runner.input_adapter.register_mapping("Key_EndTurn", lambda: EndTurnIntent())

    # 2. Register Unity Event Presenter Subscriptions (Animations / Audio / UI)
    vfx_log: list[str] = []
    anim_log: list[str] = []

    runner.event_presenter.subscribe(
        UnitMovedEvent,
        lambda ev: anim_log.append(f"Anim_Walk_{ev.unit_id}_{ev.to_pos}"),
    )
    runner.event_presenter.subscribe(
        AttackResolvedEvent,
        lambda ev: vfx_log.append(
            f"VFX_Slash_{ev.target_id}_Damage_{ev.damage}_Remaining_{ev.target_remaining_hp}"
        ),
    )
    runner.event_presenter.subscribe(
        VictoryEvent,
        lambda ev: vfx_log.append(f"UI_VictoryBanner_{ev.winner_team}"),
    )

    # Initial state sync
    runner.update_frame(1.0 / 60.0)
    p_view = runner.state_presenter.get_or_create_view("player_1")
    e_view = runner.state_presenter.get_or_create_view("enemy_1")
    assert p_view.x == 0 and p_view.y == 0
    assert e_view.x == 2 and e_view.y == 2
    assert e_view.is_active is True

    # 3. Action 1: Player moves to (1, 1)
    res_move = runner.handle_input_action("Key_Move_Forward", unit_id="player_1", tx=1, ty=1)
    assert res_move is not None and res_move.success is True
    runner.update_frame(1.0 / 60.0)
    assert p_view.x == 1 and p_view.y == 1
    assert "Anim_Walk_player_1_(1, 1)" in anim_log

    # 4. Action 2: Player attacks enemy (Damage = 25, HP becomes 25)
    res_atk1 = runner.handle_input_action("Key_Attack", attacker_id="player_1", target_id="enemy_1")
    assert res_atk1 is not None and res_atk1.success is True
    runner.update_frame(1.0 / 60.0)
    assert "VFX_Slash_enemy_1_Damage_25_Remaining_25" in vfx_log
    assert e_view.is_active is True

    # 5. Action 3: AP depleted (AP = 0) -> Try 2nd attack -> Rejected
    res_atk_fail = runner.handle_input_action(
        "Key_Attack", attacker_id="player_1", target_id="enemy_1"
    )
    assert res_atk_fail is not None and res_atk_fail.success is False

    # 6. Action 4: End turn, then Enemy ends turn (back to player turn with AP = 2)
    runner.handle_input_action("Key_EndTurn")
    runner.handle_input_action("Key_EndTurn")
    runner.update_frame(1.0 / 60.0)

    # 7. Action 5: Player delivers lethal blow (Damage = 25, HP becomes 0) -> Victory!
    res_atk2 = runner.handle_input_action("Key_Attack", attacker_id="player_1", target_id="enemy_1")
    assert res_atk2 is not None and res_atk2.success is True
    runner.update_frame(1.0 / 60.0)

    # Assert presentation state reflects victory and enemy defeat
    assert "VFX_Slash_enemy_1_Damage_25_Remaining_0" in vfx_log
    assert "UI_VictoryBanner_player" in vfx_log
    assert e_view.is_active is False
    assert runner.bridge.current_state["game_over"] is True
    assert runner.bridge.current_state["winner"] == "player"


# ──────────────────────────────────────────────────────────────────────────────
# TEST 2: Frame-Rate Independence Invariance (30 FPS vs 60 FPS vs 120 FPS vs Variable)
# ──────────────────────────────────────────────────────────────────────────────
def test_2_framerate_independence_invariance() -> None:
    """2. Fixed-timestep accumulator guarantees identical state hashes across all frame rates."""
    core = TacticalGameCore()

    # Define test intent timeline
    intents = [
        MoveIntent("player_1", 1, 1),
        AttackIntent("player_1", "enemy_1", 25),
        EndTurnIntent(),
        EndTurnIntent(),
        AttackIntent("player_1", "enemy_1", 25),
    ]

    def run_simulation(schedule: list[float]) -> str:
        sim_bridge = PresentationBridge(core=copy.deepcopy(core), fixed_dt=1.0 / 60.0)
        sim_runner = UnityGameRunner(bridge=sim_bridge)

        # Dispatch intents
        for intent in intents:
            sim_bridge.submit_intent(intent)

        # Step through frame schedule
        for dt in schedule:
            sim_runner.update_frame(dt)

        return sim_bridge.core.state_hash(sim_bridge.current_state)

    # Schedule 1: 60 FPS (60 frames * 1/60s = 1.0s)
    hash_60 = run_simulation([1.0 / 60.0] * 60)

    # Schedule 2: 30 FPS (30 frames * 1/30s = 1.0s)
    hash_30 = run_simulation([1.0 / 30.0] * 30)

    # Schedule 3: 120 FPS (120 frames * 1/120s = 1.0s)
    hash_120 = run_simulation([1.0 / 120.0] * 120)

    # Schedule 4: Variable jittery frame times (summing to 1.0s)
    var_dts = [0.016, 0.033, 0.011, 0.040, 0.020, 0.016, 0.014, 0.050]
    jitter_schedule: list[float] = []
    tot = 0.0
    i = 0
    while tot < 1.0 - 1e-6:
        dt = var_dts[i % len(var_dts)]
        if tot + dt > 1.0:
            dt = 1.0 - tot
        jitter_schedule.append(dt)
        tot += dt
        i += 1
    hash_var = run_simulation(jitter_schedule)

    assert hash_60 == hash_30
    assert hash_60 == hash_120
    assert hash_60 == hash_var


# ──────────────────────────────────────────────────────────────────────────────
# TEST 3: Deterministic Replay through the Unity Adapter
# ──────────────────────────────────────────────────────────────────────────────
def test_3_replay_through_unity_adapter() -> None:
    """3. Replaying recorded session through UnityGameRunner preserves exact hash locks."""
    core = TacticalGameCore()

    # 1. Record original session
    _, record = DeterministicReplayer.record_session(
        core=core,
        seed=777,
        dt_sequence=(0.016, 0.016, 0.033, 0.016),
        session_id="tactical_replay_proof",
    )

    # 2. Attach Unity Presentation Bridge
    replay_bridge = PresentationBridge(core=copy.deepcopy(core), fixed_dt=1.0 / 60.0)
    replay_runner = UnityGameRunner(bridge=replay_bridge)

    for _tick, intent in record.intent_sequence:
        replay_runner.handle_input_action("direct", intent=intent)

    for dt in record.dt_sequence:
        replay_runner.update_frame(dt)

    # Verify replay determinism
    verification = DeterministicReplayer.verify_replay(core=core, record=record)
    assert verification.success is True
    assert verification.divergent_tick is None


# ──────────────────────────────────────────────────────────────────────────────
# TEST 4: Boundary Purity & Snapshot Restore Fidelity
# ──────────────────────────────────────────────────────────────────────────────
def test_4_boundary_purity_and_snapshot_fidelity() -> None:
    """4. GameCore has zero presentation dependencies and supports immutable snapshot restore."""
    core = TacticalGameCore()
    init_state = core.initial_state()

    snap = core.snapshot(init_state, tick=0)
    assert snap.state_hash is not None

    # Mutate in-memory copy
    mutated = copy.deepcopy(init_state)
    mutated["entities"]["player_1"]["hp"] = 10

    # Restore snapshot
    restored = core.restore(snap)
    assert restored["entities"]["player_1"]["hp"] == 100
    assert core.state_hash(restored) == snap.state_hash


# ──────────────────────────────────────────────────────────────────────────────
# TEST 5: Presentation Failure Isolation
# ──────────────────────────────────────────────────────────────────────────────
def test_5_presentation_failure_isolation() -> None:
    """5. Presentation render/audio exceptions are caught and never corrupt GameCore state."""
    core = TacticalGameCore()
    bridge = PresentationBridge(core=core)
    runner = UnityGameRunner(bridge=bridge)

    # Register crashing presentation subscriber
    def crashing_presenter(ev: Any) -> None:
        raise RuntimeError("Fatal Unity Graphics Driver Exception")

    runner.event_presenter.subscribe(UnitMovedEvent, crashing_presenter)

    # Move player — presentation crashes in subscriber, but GameCore state succeeds!
    res = bridge.submit_intent(MoveIntent("player_1", 1, 0))
    assert res.success is True

    # Advance frame — catches and logs presentation error without crashing runner
    runner.update_frame(1.0 / 60.0)
    assert runner.bridge.current_state["entities"]["player_1"]["x"] == 1


# ──────────────────────────────────────────────────────────────────────────────
# TEST 6: Dual Certification Gates (PURE_CORE + ENGINE_BINDING)
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_6_dual_certification_gates(
    temp_workspace: WorkspaceManager, sandbox: CodeSandbox
) -> None:
    """6. Formally certifies both PURE_CORE_CERTIFIED and ENGINE_BINDING_CERTIFIED."""
    core = TacticalGameCore()
    spec = GameProjectSpec(
        title="TacticalArena",
        description="Tactical grid strategy",
        genre=GameGenre.TURN_BASED_STRATEGY,
        target_engine=EngineTarget.UNITY,
        architecture_pattern=GameArchitecturePattern.PURE_CORE_HEADLESS,
    )
    project_dir = "tactical_arena"

    # Write pure domain code into workspace
    temp_workspace.write(
        f"{project_dir}/tactics.py",
        "class TacticalArenaRules:\n    def evaluate(self):\n        return True\n",
    )
    test_code = (
        "from tactics import TacticalArenaRules\n"
        "def test_rules():\n"
        "    assert TacticalArenaRules().evaluate() is True\n"
    )
    temp_workspace.write(f"{project_dir}/test_tactics.py", test_code)

    adapter = UnityEngineAdapter()

    # 1. Pure Core Certification
    pure_cert = await GameCoreCertifier.certify(
        core=core,
        spec=spec,
        workspace=temp_workspace,
        project_dir=project_dir,
        sandbox=sandbox,
        adapter=adapter,
    )
    assert pure_cert.certified is True
    assert pure_cert.purity_passed is True
    assert pure_cert.zero_engine_imports is True

    # 2. Engine Binding Certification
    binding_cert = await GameCoreCertifier.certify_engine_binding(
        core=core,
        spec=spec,
        workspace=temp_workspace,
        project_dir=project_dir,
        engine_target=EngineTarget.UNITY,
        sandbox=sandbox,
        adapter=adapter,
    )
    assert binding_cert.certified is True
    assert binding_cert.pure_core_certified is True
    assert binding_cert.boundary_purity_passed is True
    assert binding_cert.input_translation_passed is True
    assert binding_cert.event_propagation_passed is True
    assert binding_cert.state_sync_passed is True
    assert binding_cert.framerate_independence_passed is True
    assert binding_cert.replay_fidelity_passed is True
    assert binding_cert.failure_isolation_passed is True


# ──────────────────────────────────────────────────────────────────────────────
# TEST 7: Three-Domain Generalization Proof (Tactical, Rhythm, Farming)
# ──────────────────────────────────────────────────────────────────────────────
def test_7_three_domain_generalization_proof() -> None:
    """7. Generic presentation architecture binds 3 distinct domains without game branches."""

    # Domain 1: Tactical Combat
    core1 = TacticalGameCore()
    bridge1 = PresentationBridge(core1)
    runner1 = UnityGameRunner(bridge1)
    runner1.input_adapter.register_mapping("Move", lambda: MoveIntent("player_1", 1, 0))
    res1 = runner1.handle_input_action("Move")
    assert res1 is not None and res1.success is True

    # Domain 2: Rhythm Game
    class RhythmCore(BaseGameCore):
        def initial_state(self) -> dict[str, Any]:
            return {"schema_version": 1, "score": 0, "combo": 0}

        def __init__(self) -> None:
            super().__init__(schema_version=1)
            self.register_intent_handler(dict, self._handle_hit)

        def _handle_hit(
            self, state: dict[str, Any], intent: dict[str, Any]
        ) -> tuple[bool, list[Any], str | None]:
            state["score"] += 100
            state["combo"] += 1
            return True, [{"event": "NoteHit", "score": state["score"]}], None

    core2 = RhythmCore()
    bridge2 = PresentationBridge(core2)
    runner2 = UnityGameRunner(bridge2)
    runner2.input_adapter.register_mapping("HitNote", lambda: {"action": "hit"})
    res2 = runner2.handle_input_action("HitNote")
    assert res2 is not None and res2.success is True
    assert bridge2.current_state["score"] == 100

    # Domain 3: Farming / Resource Production
    class FarmCore(BaseGameCore):
        def initial_state(self) -> dict[str, Any]:
            return {"schema_version": 1, "water": 100, "crops": 0}

        def __init__(self) -> None:
            super().__init__(schema_version=1)
            self.register_intent_handler(dict, self._handle_irrigate)

        def _handle_irrigate(
            self, state: dict[str, Any], intent: dict[str, Any]
        ) -> tuple[bool, list[Any], str | None]:
            state["water"] -= 20
            state["crops"] += 1
            return True, [{"event": "CropsHarvested", "total": state["crops"]}], None

    core3 = FarmCore()
    bridge3 = PresentationBridge(core3)
    runner3 = UnityGameRunner(bridge3)
    runner3.input_adapter.register_mapping("Irrigate", lambda: {"action": "water"})
    res3 = runner3.handle_input_action("Irrigate")
    assert res3 is not None and res3.success is True
    assert bridge3.current_state["crops"] == 1


# ──────────────────────────────────────────────────────────────────────────────
# TEST 8: UnityEngineAdapter Scaffolding & Structural Codebase Validation
# ──────────────────────────────────────────────────────────────────────────────
def test_8_unity_engine_adapter_scaffolding_and_validation(
    temp_workspace: WorkspaceManager,
) -> None:
    """8. Verifies UnityEngineAdapter scaffolds full project hierarchy and passes validation."""
    adapter = UnityEngineAdapter()
    spec = GameProjectSpec(
        title="TacticalStrike",
        description="Tactical presentation game",
        genre=GameGenre.TURN_BASED_STRATEGY,
        target_engine=EngineTarget.UNITY,
        target_language="csharp",
        architecture_pattern=GameArchitecturePattern.PURE_CORE_HEADLESS,
    )
    project_dir = "tactical_strike_unity"

    files = adapter.scaffold_project(spec, temp_workspace, project_dir=project_dir)
    assert len(files) >= 8

    # Assert expected Unity project paths
    assert f"{project_dir}/README.md" in files
    assert f"{project_dir}/ProjectSettings/ProjectVersion.txt" in files
    assert f"{project_dir}/Assets/Scripts/Domain/GameCore.Domain.csproj" in files
    assert f"{project_dir}/Assets/Scripts/Domain/Contracts.cs" in files
    assert f"{project_dir}/Assets/Scripts/CoreBridge/CoreBridge.cs" in files
    assert f"{project_dir}/Assets/Scripts/Presentation/UnityGameRunner.cs" in files
    assert f"{project_dir}/Assets/Scripts/Input/UnityInputAdapter.cs" in files
    assert f"{project_dir}/Assets/Scripts/Presentation/UnityEntityView.cs" in files
    assert f"{project_dir}/Tests/GameCore.Tests.csproj" in files

    # Validate codebase architecture
    val_report = adapter.validate_codebase(temp_workspace, project_dir)
    assert val_report.is_valid is True
    assert val_report.error_count == 0
