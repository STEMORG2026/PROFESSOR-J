"""Tests for the Phase 9a DatabaseEngine + persistence repositories."""

from __future__ import annotations

from pathlib import Path

from app.db import (
    MasteryRepository,
    SqliteDatabaseEngine,
    TranscriptRepository,
)
from app.domain.learner import MasteryScore


def _engine(tmp_path: Path) -> SqliteDatabaseEngine:
    eng = SqliteDatabaseEngine(tmp_path / "test.db")
    eng.create_schema()
    return eng


class TestMasteryRepository:
    def test_upsert_and_load_round_trip(self, tmp_path: Path) -> None:
        eng = _engine(tmp_path)
        repo = MasteryRepository(eng)
        repo.upsert(
            "learner-1",
            MasteryScore(concept_id="lhs:phys.force", score=0.9, practice_count=2, correct_count=2),
        )
        loaded = repo.load_for("learner-1")
        assert "lhs:phys.force" in loaded
        assert loaded["lhs:phys.force"].score == 0.9
        assert loaded["lhs:phys.force"].practice_count == 2
        eng.dispose()

    def test_upsert_updates_existing(self, tmp_path: Path) -> None:
        eng = _engine(tmp_path)
        repo = MasteryRepository(eng)
        repo.upsert("l", MasteryScore(concept_id="c", score=0.5, practice_count=1, correct_count=1))
        repo.upsert("l", MasteryScore(concept_id="c", score=0.8, practice_count=2, correct_count=2))
        loaded = repo.load_for("l")
        assert loaded["c"].score == 0.8
        assert loaded["c"].practice_count == 2
        eng.dispose()

    def test_load_empty_returns_empty(self, tmp_path: Path) -> None:
        eng = _engine(tmp_path)
        assert MasteryRepository(eng).load_for("nobody") == {}
        eng.dispose()


class TestTranscriptRepository:
    def test_append_and_history(self, tmp_path: Path) -> None:
        eng = _engine(tmp_path)
        repo = TranscriptRepository(eng)
        repo.append("sess-1", "l", "user", "hello")
        repo.append("sess-1", "l", "assistant", "hi there", grounded=True)
        history = list(reversed(repo.history("sess-1")))  # history returns newest-first
        assert [h["role"] for h in history] == ["user", "assistant"]
        assert history[1]["grounded"] is True
        eng.dispose()

    def test_history_does_not_leak_other_sessions(self, tmp_path: Path) -> None:
        eng = _engine(tmp_path)
        repo = TranscriptRepository(eng)
        repo.append("sess-1", "l", "user", "a")
        repo.append("sess-2", "l", "user", "b")
        assert [h["content"] for h in repo.history("sess-1")] == ["a"]
        eng.dispose()
