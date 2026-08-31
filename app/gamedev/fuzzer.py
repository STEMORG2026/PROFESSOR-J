"""Property-Based & Fuzz Verification Facility for GameCore.

Generates randomized, adversarial intent sequences and verifies that declared domain
invariants hold unconditionally across all transitions without domain-specific hardcoding.
"""

from __future__ import annotations

import copy
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.gamedev.core import GameCoreProtocol
from app.gamedev.primitives import SeededPRNGStream

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FuzzResult:
    """Outcome of a property-based fuzz execution run."""

    passed: bool
    iterations_completed: int
    seed: int
    invariants_evaluated: int
    violations_found: tuple[str, ...] = field(default_factory=tuple)
    failing_intent: str | None = None
    failing_tick: int | None = None
    failing_state_snapshot: dict[str, Any] | None = None
    reproduction_trace: tuple[str, ...] = field(default_factory=tuple)


class GameCoreFuzzer:
    """Adversarial property fuzzer for engine-neutral GameCore implementations."""

    @classmethod
    def fuzz(
        cls,
        core: GameCoreProtocol,
        intent_generator: Callable[[int, SeededPRNGStream], Any],
        seed: int = 42,
        iterations: int = 200,
        dt_choices: Sequence[float] = (0.016, 0.033, 0.1, 0.5, 0.0, -0.01),
    ) -> FuzzResult:
        """Execute adversarial fuzzing against core, verifying domain invariants after each step."""
        prng = SeededPRNGStream(seed=seed, stream_name="fuzzer")
        state = core.initial_state()

        trace_log: list[str] = []
        invariants_checked = 0

        for i in range(iterations):
            tick = state.get("tick", i)

            # 1. Invariant check before action
            ok, violations = core.verify_invariants(state)
            invariants_checked += 1
            if not ok:
                return FuzzResult(
                    passed=False,
                    iterations_completed=i,
                    seed=seed,
                    invariants_evaluated=invariants_checked,
                    violations_found=violations,
                    failing_tick=tick,
                    failing_state_snapshot=copy.deepcopy(state),
                    reproduction_trace=tuple(trace_log),
                )

            # 2. Decision: generate intent or advance timestep
            action_type = prng.choice(["intent", "step", "both"])

            if action_type in {"intent", "both"}:
                intent = intent_generator(i, prng)
                intent_repr = f"Intent(type={type(intent).__name__}, repr={intent})"
                trace_log.append(intent_repr)

                res = core.apply_intent(state, intent)
                if res.success:
                    state = res.new_state
                # Check invariants immediately after intent
                ok, violations = core.verify_invariants(state)
                invariants_checked += 1
                if not ok:
                    return FuzzResult(
                        passed=False,
                        iterations_completed=i,
                        seed=seed,
                        invariants_evaluated=invariants_checked,
                        violations_found=violations,
                        failing_intent=intent_repr,
                        failing_tick=state.get("tick", tick),
                        failing_state_snapshot=copy.deepcopy(state),
                        reproduction_trace=tuple(trace_log),
                    )

            if action_type in {"step", "both"}:
                dt = prng.choice(dt_choices)
                step_repr = f"Step(dt={dt})"
                trace_log.append(step_repr)

                step_res = core.step(state, dt)
                state = step_res.new_state

                # Check invariants immediately after timestep
                ok, violations = core.verify_invariants(state)
                invariants_checked += 1
                if not ok:
                    return FuzzResult(
                        passed=False,
                        iterations_completed=i,
                        seed=seed,
                        invariants_evaluated=invariants_checked,
                        violations_found=violations,
                        failing_intent=step_repr,
                        failing_tick=state.get("tick", tick),
                        failing_state_snapshot=copy.deepcopy(state),
                        reproduction_trace=tuple(trace_log),
                    )

        return FuzzResult(
            passed=True,
            iterations_completed=iterations,
            seed=seed,
            invariants_evaluated=invariants_checked,
            reproduction_trace=tuple(trace_log[-10:]),
        )


__all__ = [
    "FuzzResult",
    "GameCoreFuzzer",
]
