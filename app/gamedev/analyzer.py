"""Game Project Analyzer — Extracts structural models from game workspaces.

Enables PROFESSOR-J to inspect and understand arbitrary, unfamiliar game codebases
without assuming specific genres, engines, or rules.
"""

from __future__ import annotations

import logging
import re

from app.domain.gamedev import (
    EngineTarget,
    GameArchitecturePattern,
    GameProjectModel,
)
from app.workspace.workspace import WorkspaceManager

logger = logging.getLogger(__name__)


class GameProjectAnalyzer:
    """Extracts a structured GameProjectModel from an arbitrary workspace directory."""

    @staticmethod
    def analyze_project(
        workspace: WorkspaceManager,
        project_dir: str = "",
    ) -> GameProjectModel:
        """Inspect workspace files and extract structural domain and architecture metadata."""
        resolved_root = workspace._resolve(project_dir)
        project_name = resolved_root.name or "GameProject"

        ignored_extensions = {".pyc", ".pyo", ".pyd", ".dll", ".so", ".dylib", ".exe", ".bin"}
        source_files: list[str] = []
        test_files: list[str] = []
        detected_systems: list[str] = []
        state_models: list[str] = []
        intent_handlers: list[str] = []
        events_emitted: list[str] = []
        schema_version = 1
        is_pure_core = True

        if not resolved_root.exists():
            return GameProjectModel(
                project_name=project_name,
                root_dir=project_dir,
                is_pure_core=True,
            )

        for p in resolved_root.glob("**/*"):
            if not p.is_file() or p.suffix in ignored_extensions or "__pycache__" in p.parts:
                continue

            rel = str(p.relative_to(workspace.root))
            if "test_" in p.name or "tests" in rel or "Tests" in p.name:
                test_files.append(rel)
            else:
                source_files.append(rel)

            res = workspace.read(rel)
            if not res.get("success"):
                continue

            content = res.get("content", "")

            # Check engine pollution
            if "UnityEngine" in content or "Godot" in content or "Unreal" in content:
                is_pure_core = False

            # Detect systems (class names ending in Manager, System, Engine, Board, Rng, Fsm, Bus)
            system_matches = re.findall(
                r"class\s+([A-Za-z0-9_]*(?:Manager|System|Engine|Board|Rng|Fsm|Bus|State|Deck|Sim))",
                content,
            )
            for s in system_matches:
                if s not in detected_systems and not s.startswith("Test"):
                    detected_systems.append(s)

            # Detect state models
            state_matches = re.findall(r"class\s+([A-Za-z0-9_]*State[A-Za-z0-9_]*)", content)
            for st in state_matches:
                if st not in state_models:
                    state_models.append(st)

            # Detect intents / commands
            intent_matches = re.findall(
                r"class\s+([A-Za-z0-9_]*(?:Intent|Command|Action))\b", content
            )
            for it in intent_matches:
                if it not in intent_handlers:
                    intent_handlers.append(it)

            # Detect events
            event_matches = re.findall(r"class\s+([A-Za-z0-9_]*Event)\b", content)
            for ev in event_matches:
                if ev not in events_emitted:
                    events_emitted.append(ev)

            # Detect schema version
            ver_match = re.search(r"schema_version\s*[:=]\s*(\d+)", content)
            if ver_match:
                schema_version = max(schema_version, int(ver_match.group(1)))

        # Deduce architecture pattern
        pattern = GameArchitecturePattern.PURE_CORE_HEADLESS
        if any("Event" in s for s in events_emitted) or any("Fsm" in s for s in detected_systems):
            pattern = GameArchitecturePattern.STATE_MACHINE_EVENT_DRIVEN

        return GameProjectModel(
            project_name=project_name,
            root_dir=project_dir,
            architecture_pattern=pattern,
            detected_systems=tuple(sorted(detected_systems)),
            state_models=tuple(sorted(state_models)),
            intent_handlers=tuple(sorted(intent_handlers)),
            events_emitted=tuple(sorted(events_emitted)),
            test_files=tuple(sorted(test_files)),
            source_files=tuple(sorted(source_files)),
            schema_version=schema_version,
            engine_target=EngineTarget.PURE_CORE,
            is_pure_core=is_pure_core,
            metadata={"source_file_count": len(source_files), "test_file_count": len(test_files)},
        )


__all__ = ["GameProjectAnalyzer"]
