# Deterministic Replay & Simulation Hashing

## Overview

The `DeterministicReplayer` facility records and verifies exact simulation sessions to guarantee reproducibility across development runs, engine adapters, and headless verification suites.

## Replay Record

A `ReplayRecord` contains:
- `record_id`: Unique session identifier.
- `seed`: Initial random seed for `SeededPRNGStream`.
- `initial_state`: Initial state dictionary.
- `intent_sequence`: Sequence of `(tick, intent)` dispatched during the session.
- `tick_count`: Total simulation ticks.
- `dt_sequence`: Monotonic sequence of continuous timestep deltas.
- `state_hashes`: Canonical SHA-256 state hashes recorded after each step.
- `events_emitted`: Sequence of emitted domain events.

## Divergence Detection

During `verify_replay`:
1. The GameCore is initialized with `record.initial_state` and `record.seed`.
2. Steps and intents are executed in lockstep using `record.dt_sequence` and `record.intent_sequence`.
3. At each tick, the resulting state hash is compared against `record.state_hashes[tick]`.
4. Any mismatch in state hash or event sequence is immediately flagged with divergence telemetry and tick location.
