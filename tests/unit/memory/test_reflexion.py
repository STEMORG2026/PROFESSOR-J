"""Tests for ReflexionEngine + the bootstrap composition root."""

from __future__ import annotations

from pathlib import Path

from app.bootstrap import build_root
from app.domain.learner import EvaluationResult
from app.memory import InMemoryBackend, ReflexionEngine

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "lhs_knowledge_fixture.json"


class TestReflexionEngine:
    def test_misconception_reflection(self) -> None:
        engine = ReflexionEngine(InMemoryBackend())
        r = engine.reflect(
            "l1", "lhs:phys.force", "incorrect", detected_misconception="heavier_falls_faster"
        )
        assert r.kind == "misconception"
        assert "heavier_falls_faster" in r.summary

    def test_correct_reflection(self) -> None:
        engine = ReflexionEngine(InMemoryBackend())
        r = engine.reflect("l1", "lhs:phys.force", EvaluationResult.CORRECT)
        assert r.kind == "reinforcement"

    def test_incorrect_reflection(self) -> None:
        engine = ReflexionEngine(InMemoryBackend())
        r = engine.reflect("l1", "lhs:phys.force", "incorrect")
        assert r.kind == "correction"

    def test_lessons_namespaced_per_learner(self) -> None:
        engine = ReflexionEngine(InMemoryBackend())
        engine.reflect("l1", "c", "incorrect")
        engine.reflect("l2", "c", EvaluationResult.CORRECT)
        lessons = engine.lessons("l1")
        assert lessons and lessons[0]["kind"] == "correction"


class TestBootstrap:
    def test_build_root_wires_everything(self, tmp_path: Path) -> None:
        root = build_root(
            db_path=str(tmp_path / "app.db"),
            lhs_export=str(FIXTURE),
            workspace_root=str(tmp_path / "ws"),
        )
        assert root.sessions is not None
        assert root.memory is not None
        assert root.tools.has_tool("run_code")
        assert root.tools.has_tool("solve_math")
        assert root.mastery is not None
        assert root.transcripts is not None
        root.db.dispose()

    def test_health_reports_ready(self, tmp_path: Path) -> None:
        root = build_root(
            db_path=str(tmp_path / "app.db"),
            lhs_export=str(FIXTURE),
            workspace_root=str(tmp_path / "ws"),
        )
        health = root.health()
        assert health["ready"] is True
        assert health["db"] is True
        root.db.dispose()
