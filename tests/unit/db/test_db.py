"""Tests for the Phase 9a DatabaseEngine + persistence repositories."""

from __future__ import annotations

from pathlib import Path

from app.db import (
    MasteryRepository,
    SessionRepository,
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


class TestSessionRepository:
    def test_create_and_get_round_trip(self, tmp_path: Path) -> None:
        eng = _engine(tmp_path)
        repo = SessionRepository(eng)
        repo.create_session(
            "sess-1",
            "learner-1",
            title="Physics help",
            system_prompt="You are a Socratic tutor",
            provider="singularity",
            model="deepseek-v4-flash-0731",
            api_keys='{"singularity": "sk-test"}',
            base_url="https://api.singularityapi.dev/v1",
        )
        s = repo.get_session("sess-1")
        assert s is not None
        assert s["session_id"] == "sess-1"
        assert s["learner_id"] == "learner-1"
        assert s["title"] == "Physics help"
        assert s["status"] == "active"
        assert s["provider"] == "singularity"
        assert s["model"] == "deepseek-v4-flash-0731"
        assert s["api_keys"] == '{"singularity": "sk-test"}'
        assert s["base_url"] == "https://api.singularityapi.dev/v1"
        eng.dispose()

    def test_get_missing_returns_none(self, tmp_path: Path) -> None:
        eng = _engine(tmp_path)
        assert SessionRepository(eng).get_session("nope") is None
        eng.dispose()

    def test_list_sessions_is_scoped_to_learner(self, tmp_path: Path) -> None:
        eng = _engine(tmp_path)
        repo = SessionRepository(eng)
        repo.create_session("s1", "alice", title="A")
        repo.create_session("s2", "alice", title="B")
        repo.create_session("s3", "bob", title="C")
        alice = repo.list_sessions("alice")
        ids = {s["session_id"] for s in alice}
        assert ids == {"s1", "s2"}
        assert all(s["learner_id"] == "alice" for s in alice)
        eng.dispose()

    def test_update_session_only_touches_given_fields(self, tmp_path: Path) -> None:
        eng = _engine(tmp_path)
        repo = SessionRepository(eng)
        repo.create_session("s1", "alice", provider="old", model="m1")
        repo.update_session("s1", provider="singularity", model="deepseek-v4-flash-0731")
        s = repo.get_session("s1")
        assert s is not None
        assert s["provider"] == "singularity"
        assert s["model"] == "deepseek-v4-flash-0731"
        # Untouched fields keep their original values.
        assert s["learner_id"] == "alice"
        assert s["status"] == "active"
        # A no-op update (all kwargs None) is safe.
        repo.update_session("s1")
        eng.dispose()

    def test_delete_session_removes_conversations(self, tmp_path: Path) -> None:
        eng = _engine(tmp_path)
        repo = SessionRepository(eng)
        repo.create_session("s1", "alice")
        repo.create_conversation(
            "c1", "s1", title="t", messages=[{"role": "user", "content": "hi"}]
        )
        repo.delete_session("s1")
        assert repo.get_session("s1") is None
        assert repo.get_conversation("c1") is None
        eng.dispose()

    def test_conversation_round_trip(self, tmp_path: Path) -> None:
        eng = _engine(tmp_path)
        repo = SessionRepository(eng)
        repo.create_session("s1", "alice")
        msgs = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
        repo.create_conversation("c1", "s1", title="chat", messages=msgs)
        conv = repo.get_conversation("c1")
        assert conv is not None
        assert conv["session_id"] == "s1"
        assert conv["title"] == "chat"
        assert conv["messages"] == msgs
        repo.update_conversation("c1", messages=[{"role": "user", "content": "bye"}])
        updated = repo.get_conversation("c1")
        assert updated is not None
        assert updated["messages"] == [{"role": "user", "content": "bye"}]
        assert repo.list_conversations("s1")[0]["conversation_id"] == "c1"
        repo.delete_conversation("c1")
        assert repo.get_conversation("c1") is None
        eng.dispose()

    def test_settings_upsert_and_defaults(self, tmp_path: Path) -> None:
        eng = _engine(tmp_path)
        repo = SessionRepository(eng)
        assert repo.get_setting("theme") is None
        repo.set_setting("theme", "dark")
        repo.set_setting("theme", "light")  # upsert overwrites
        assert repo.get_setting("theme") == "light"
        repo.set_default("provider", "singularity")
        assert repo.get_default("provider") == "singularity"
        keys = {k for k, _ in repo.list_settings()}
        assert "theme" in keys and "default_provider" in keys
        eng.dispose()

    def test_persona_crud(self, tmp_path: Path) -> None:
        eng = _engine(tmp_path)
        repo = SessionRepository(eng)
        repo.create_persona("p1", "Tutor", "You are a tutor", description="Friendly tutor")
        p = repo.get_persona("p1")
        assert p is not None
        assert p["name"] == "Tutor"
        assert p["description"] == "Friendly tutor"
        assert p["system_prompt"] == "You are a tutor"
        repo.update_persona("p1", system_prompt="You are a strict tutor")
        updated = repo.get_persona("p1")
        assert updated is not None
        assert updated["system_prompt"] == "You are a strict tutor"
        assert {p["persona_id"] for p in repo.list_personas()} == {"p1"}
        repo.delete_persona("p1")
        assert repo.get_persona("p1") is None
        eng.dispose()
