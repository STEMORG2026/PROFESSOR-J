"""Engine-Neutral Presentation Adapter Contract & Unity Presentation Architecture.

Defines the formal boundary between pure GameCore and downstream presentation layers:
- The GameCore never imports or references presentation adapters.
- Presentation adapters consume state snapshots and domain events, and submit intents.
- PresentationBridge provides fixed accumulation guaranteeing frame-rate independence.
- UnityGameRunner, UnityInputAdapter, UnityEventPresenter, and UnityStatePresenter provide
  complete presentation bindings without polluting domain rules.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from app.domain.gamedev import IntentResult, StepResult
from app.gamedev.core import GameCoreProtocol

logger = logging.getLogger(__name__)


@runtime_checkable
class PresentationAdapterProtocol(Protocol):
    """Protocol implemented by engine presentation adapters (Unity, Godot, Fake)."""

    def observe_state(self, state: dict[str, Any]) -> None:
        """Observe new or updated state snapshot emitted by GameCore."""
        ...

    def submit_intent(self, intent: Any) -> IntentResult:
        """Submit user/AI input intent to GameCore for deterministic processing."""
        ...

    def poll_events(self) -> list[Any]:
        """Drain queued domain events received from GameCore."""
        ...

    def drive_tick(self, dt: float) -> StepResult:
        """Drive one fixed simulation timestep on GameCore."""
        ...


class PresentationBridge:
    """Bridges an engine-neutral GameCore with a PresentationAdapter.

    Maintains a deterministic fixed-step accumulator so that presentation frame rates
    (30 FPS, 60 FPS, 120 FPS, variable) never alter the logical simulation sequence.
    """

    def __init__(self, core: GameCoreProtocol, fixed_dt: float = 1.0 / 60.0) -> None:
        self.core = core
        self.fixed_dt = fixed_dt
        self.current_state = core.initial_state()
        self._event_queue: list[Any] = []
        self._accumulator: float = 0.0
        self.total_simulation_time: float = 0.0

    def submit_intent(self, intent: Any) -> IntentResult:
        """Forward input intent to GameCore."""
        res = self.core.apply_intent(self.current_state, intent)
        if res.success:
            self.current_state = res.new_state
            if res.events:
                self._event_queue.extend(res.events)
        return res

    def advance_time(self, dt: float) -> StepResult:
        """Advance GameCore by a discrete timestep dt and collect events."""
        res = self.core.step(self.current_state, dt)
        self.current_state = res.new_state
        self.total_simulation_time += dt
        if res.events:
            self._event_queue.extend(res.events)
        return res

    def advance_frame(self, frame_dt: float) -> list[StepResult]:
        """Advance simulation time using a deterministic fixed-step accumulator.

        Guarantees identical GameCore simulation steps regardless of whether
        presentation runs at 30 FPS, 60 FPS, 120 FPS, or variable frame rate.
        """
        self._accumulator += frame_dt
        step_results: list[StepResult] = []
        # Use small epsilon to prevent precision drift
        while self._accumulator >= self.fixed_dt - 1e-9:
            step_res = self.advance_time(self.fixed_dt)
            step_results.append(step_res)
            self._accumulator -= self.fixed_dt
        return step_results

    def drain_events(self) -> list[Any]:
        """Drain all pending domain events."""
        events = list(self._event_queue)
        self._event_queue.clear()
        return events

    def snapshot(self, tick: int = 0) -> Any:
        """Create an immutable state snapshot."""
        return self.core.snapshot(self.current_state, tick=tick)

    def restore(self, snapshot: Any) -> None:
        """Restore state from snapshot."""
        self.current_state = self.core.restore(snapshot)
        self._event_queue.clear()
        self._accumulator = 0.0


class UnityInputAdapter:
    """Translates engine input actions/events into pure domain intents."""

    def __init__(self) -> None:
        self._action_mappings: dict[str, Callable[..., Any]] = {}

    def register_mapping(self, action_name: str, factory: Callable[..., Any]) -> None:
        """Register mapping from an engine input action to a domain Intent factory."""
        self._action_mappings[action_name] = factory

    def translate_input(self, action_name: str, **kwargs: Any) -> Any | None:
        """Translate raw engine input trigger to domain intent."""
        factory = self._action_mappings.get(action_name)
        if not factory:
            logger.debug("No domain intent mapping for input action: %s", action_name)
            return None
        return factory(**kwargs)


class UnityEventPresenter:
    """Translates domain events into presentation reactions (VFX, SFX, UI, Mecanim)."""

    def __init__(self) -> None:
        self._handlers: dict[type, list[Callable[[Any], None]]] = {}
        self.presented_events: list[Any] = []

    def subscribe(self, event_type: type, handler: Callable[[Any], None]) -> None:
        """Subscribe presentation callback to domain event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def present_event(self, event: Any) -> None:
        """Present a domain event visually/acoustically."""
        self.presented_events.append(event)
        handlers = self._handlers.get(type(event), [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error("Presentation error handling event %s: %s", type(event).__name__, e)


class UnityEntityView:
    """Presentation representation of an in-game entity."""

    def __init__(self, entity_id: str, name: str = "") -> None:
        self.entity_id = entity_id
        self.name = name or entity_id
        self.x: float = 0.0
        self.y: float = 0.0
        self.z: float = 0.0
        self.is_active: bool = True
        self.visual_properties: dict[str, Any] = {}
        self.played_animations: list[str] = []

    def update_transform(self, x: float, y: float, z: float = 0.0) -> None:
        """Update visual transform coordinates."""
        self.x = x
        self.y = y
        self.z = z

    def trigger_animation(self, anim_name: str) -> None:
        """Record animation trigger on presentation view."""
        self.played_animations.append(anim_name)


class UnityStatePresenter:
    """Synchronizes GameCore domain state with Unity entity views and UI state."""

    def __init__(self) -> None:
        self.entity_views: dict[str, UnityEntityView] = {}
        self.latest_state: dict[str, Any] = {}
        self.sync_count: int = 0

    def get_or_create_view(self, entity_id: str, name: str = "") -> UnityEntityView:
        """Retrieve or instantiate a presentation entity view."""
        if entity_id not in self.entity_views:
            self.entity_views[entity_id] = UnityEntityView(entity_id, name)
        return self.entity_views[entity_id]

    def sync_state(self, state: dict[str, Any]) -> None:
        """Synchronize views with authoritative domain state."""
        self.latest_state = dict(state)
        self.sync_count += 1

        # Synchronize entities if present in state
        entities = state.get("entities", {})
        if isinstance(entities, dict):
            for entity_id, data in entities.items():
                if isinstance(data, dict):
                    view = self.get_or_create_view(entity_id)
                    view.update_transform(
                        x=float(data.get("x", view.x)),
                        y=float(data.get("y", view.y)),
                        z=float(data.get("z", view.z)),
                    )
                    view.is_active = bool(data.get("is_alive", True))


class UnityGameRunner:
    """Top-level Unity presentation loop manager."""

    def __init__(self, bridge: PresentationBridge) -> None:
        self.bridge = bridge
        self.input_adapter = UnityInputAdapter()
        self.event_presenter = UnityEventPresenter()
        self.state_presenter = UnityStatePresenter()
        self.frame_count: int = 0
        self.rendered_frames: list[dict[str, Any]] = []

    def handle_input_action(self, action_name: str, **kwargs: Any) -> IntentResult | None:
        """Handle raw engine input: translate to domain intent and dispatch to GameCore."""
        intent = self.input_adapter.translate_input(action_name, **kwargs)
        if intent is None:
            return None
        res = self.bridge.submit_intent(intent)
        self._process_events_and_sync()
        return res

    def update_frame(self, frame_dt: float) -> list[StepResult]:
        """Simulate Unity Update() loop with fixed-step accumulation."""
        self.frame_count += 1
        step_results = self.bridge.advance_frame(frame_dt)
        self._process_events_and_sync()
        self.rendered_frames.append(dict(self.bridge.current_state))
        return step_results

    def _process_events_and_sync(self) -> None:
        """Drain domain events and sync state presentation."""
        events = self.bridge.drain_events()
        for ev in events:
            self.event_presenter.present_event(ev)
        self.state_presenter.sync_state(self.bridge.current_state)


class FakePresentationAdapter:
    """Headless fake presentation adapter for verifying presentation bridge contracts."""

    def __init__(self, bridge: PresentationBridge) -> None:
        self.bridge = bridge
        self.rendered_frames: list[dict[str, Any]] = []
        self.observed_events: list[Any] = []
        self.total_simulated_time: float = 0.0

    def observe_state(self, state: dict[str, Any]) -> None:
        """Simulate rendering a visual frame from state."""
        self.rendered_frames.append(dict(state))

    def submit_intent(self, intent: Any) -> IntentResult:
        """Submit player or virtual controller intent."""
        res = self.bridge.submit_intent(intent)
        if res.success:
            self.observe_state(self.bridge.current_state)
        return res

    def poll_events(self) -> list[Any]:
        """Poll and collect new domain events."""
        new_events = self.bridge.drain_events()
        self.observed_events.extend(new_events)
        return new_events

    def drive_tick(self, dt: float) -> StepResult:
        """Simulate a fixed game engine update tick."""
        self.total_simulated_time += dt
        step_res = self.bridge.advance_time(dt)
        self.observe_state(step_res.new_state)
        self.poll_events()
        return step_res


__all__ = [
    "PresentationAdapterProtocol",
    "PresentationBridge",
    "UnityInputAdapter",
    "UnityEventPresenter",
    "UnityEntityView",
    "UnityStatePresenter",
    "UnityGameRunner",
    "FakePresentationAdapter",
]
