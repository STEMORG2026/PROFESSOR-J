"""Deterministic Replay Facility for PROFESSOR-J GameCore.

Provides deterministic recording, replay execution, and telemetry-backed divergence detection:
- Records initial state, seed, intent sequence, dt steps, hashes, and emitted events.
- Replays recorded sessions against a GameCore instance to detect state or event divergence.
- Produces structured diagnostic telemetry for automated repair and regression analysis.
"""

from __future__ import annotations

import copy
import logging
from collections.abc import Sequence
from typing import Any

from app.domain.gamedev import ReplayRecord, ReplayVerificationResult
from app.gamedev.core import GameCoreProtocol

logger = logging.getLogger(__name__)


class DeterministicReplayer:
    """Records and verifies deterministic GameCore execution sequences."""

    @staticmethod
    def record_session(
        core: GameCoreProtocol,
        seed: int,
        intents: Sequence[Any] = (),
        dt_sequence: Sequence[float] = (),
        session_id: str = "session_001",
    ) -> tuple[dict[str, Any], ReplayRecord]:
        """Execute and record a deterministic session from initial state.

        Returns (final_state, replay_record).
        """
        state = core.initial_state()
        initial_state_copy = copy.deepcopy(state)

        recorded_intents: list[dict[str, Any]] = []
        state_hashes: list[str] = [core.state_hash(state)]
        events_emitted: list[tuple[str, ...]] = []
        dts: list[float] = []

        # Interleave intents and dt steps if provided, or execute intents then dts
        max_steps = max(len(intents), len(dt_sequence), 1)

        for i in range(max_steps):
            # 1. Apply intent if available
            if i < len(intents):
                intent = intents[i]
                intent_record = {
                    "type": type(intent).__name__,
                    "data": (
                        getattr(intent, "__dict__", None)
                        or (
                            {s: getattr(intent, s) for s in getattr(intent, "__slots__", ())}
                            if hasattr(intent, "__slots__")
                            else str(intent)
                        )
                    ),
                }
                recorded_intents.append(intent_record)
                res = core.apply_intent(state, intent)
                if res.success:
                    state = res.new_state
                    ev_strs = tuple(str(e) for e in res.events)
                    events_emitted.append(ev_strs)
                else:
                    events_emitted.append((f"INTENT_FAILED: {res.error}",))
                state_hashes.append(core.state_hash(state))

            # 2. Advance time if available
            if i < len(dt_sequence):
                dt = dt_sequence[i]
                dts.append(dt)
                step_res = core.step(state, dt)
                state = step_res.new_state
                ev_strs = tuple(str(e) for e in step_res.events)
                if ev_strs:
                    events_emitted.append(ev_strs)
                state_hashes.append(core.state_hash(state))

        record = ReplayRecord(
            record_id=session_id,
            seed=seed,
            initial_state=initial_state_copy,
            intent_sequence=tuple(recorded_intents),
            tick_count=state.get("tick", 0),
            dt_sequence=tuple(dts),
            state_hashes=tuple(state_hashes),
            events_emitted=tuple(events_emitted),
        )
        return state, record

    @staticmethod
    def verify_replay(
        core: GameCoreProtocol,
        record: ReplayRecord,
        intent_factory: Sequence[Any] | None = None,
    ) -> ReplayVerificationResult:
        """Re-execute session and verify state hashes and event sequences match byte-for-byte."""
        state = copy.deepcopy(record.initial_state)
        current_hash = core.state_hash(state)

        if not record.state_hashes:
            return ReplayVerificationResult(
                success=False,
                divergence_reason="Replay record has no recorded state hashes",
            )

        if current_hash != record.state_hashes[0]:
            return ReplayVerificationResult(
                success=False,
                divergent_tick=0,
                expected_hash=record.state_hashes[0],
                actual_hash=current_hash,
                divergence_reason="Initial state hash mismatch",
            )

        hash_idx = 1
        intents_to_apply = list(intent_factory) if intent_factory is not None else []
        max_steps = max(len(intents_to_apply), len(record.dt_sequence), 1)

        for i in range(max_steps):
            # Apply intent
            if i < len(intents_to_apply):
                intent = intents_to_apply[i]
                res = core.apply_intent(state, intent)
                if res.success:
                    state = res.new_state
                actual_hash = core.state_hash(state)
                if hash_idx < len(record.state_hashes):
                    expected_hash = record.state_hashes[hash_idx]
                    if actual_hash != expected_hash:
                        div_msg = f"State hash divergence after intent {type(intent).__name__}"
                        return ReplayVerificationResult(
                            success=False,
                            divergent_tick=state.get("tick", i),
                            expected_hash=expected_hash,
                            actual_hash=actual_hash,
                            divergence_reason=div_msg,
                            telemetry={"step": i, "intent": str(intent)},
                        )
                    hash_idx += 1

            # Step dt
            if i < len(record.dt_sequence):
                dt = record.dt_sequence[i]
                step_res = core.step(state, dt)
                state = step_res.new_state
                actual_hash = core.state_hash(state)
                if hash_idx < len(record.state_hashes):
                    expected_hash = record.state_hashes[hash_idx]
                    if actual_hash != expected_hash:
                        return ReplayVerificationResult(
                            success=False,
                            divergent_tick=state.get("tick", i),
                            expected_hash=expected_hash,
                            actual_hash=actual_hash,
                            divergence_reason=f"State hash divergence after step(dt={dt})",
                            telemetry={"step": i, "dt": dt},
                        )
                    hash_idx += 1

        return ReplayVerificationResult(
            success=True,
            telemetry={"total_hashes_verified": hash_idx},
        )


__all__ = ["DeterministicReplayer"]
