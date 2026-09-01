"""Tests for the memory backend abstraction + MemoryService."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.memory import (
    ChromaMemoryBackend,
    InMemoryBackend,
    JsonMemoryBackend,
    MemoryService,
    MemoryStoreError,
)


class TestBackends:
    def test_in_memory_add_get_search(self) -> None:
        b = InMemoryBackend()
        b.add("a", "force equals mass times acceleration")
        b.add("b", "animal cells have no cell wall")
        assert b.get("a") is not None
        hits = b.search("acceleration force", k=2)
        assert hits and hits[0].document_id == "a"
        assert b.count() == 2

    def test_json_backend_persists(self, tmp_path: Path) -> None:
        path = tmp_path / "mem.json"
        b = JsonMemoryBackend(path)
        b.add("a", "remember me")
        b2 = JsonMemoryBackend(path)
        assert b2.get("a") is not None

    def test_chroma_backend_add_get_search(self, tmp_path: Path) -> None:
        path = tmp_path / "chroma_db"
        b = ChromaMemoryBackend(path, collection_name="test_mem")
        b.add("a", "force equals mass times acceleration")
        b.add("b", "animal cells have no cell wall")
        assert b.get("a") is not None
        hits = b.search("acceleration force", k=2)
        assert hits and hits[0].document_id == "a"
        assert b.count() == 2
        assert "a" in b
        assert "b" in b

    def test_chroma_backend_persists(self, tmp_path: Path) -> None:
        path = tmp_path / "chroma_db"
        b = ChromaMemoryBackend(path, collection_name="test_persist")
        b.add("a", "remember me")
        b2 = ChromaMemoryBackend(path, collection_name="test_persist")
        assert b2.get("a") is not None
        assert b2.count() == 1


class TestMemoryService:
    def test_namespaced_remember_and_recall(self) -> None:
        svc = MemoryService(InMemoryBackend())
        svc.remember("learner-1", "force equals mass times acceleration")
        svc.remember("learner-2", "animal cells have no cell wall")
        hits = svc.recall("learner-1", "acceleration force")
        assert hits and "acceleration" in hits[0]["text"]
        # learner-2's memories never leak into learner-1's recall.
        assert svc.recall("learner-1", "animal cell wall") == []

    def test_count_and_forget(self) -> None:
        svc = MemoryService(InMemoryBackend())
        svc.remember("learner-1", "alpha")
        svc.remember("learner-1", "beta")
        assert svc.count("learner-1") == 2
        assert svc.forget("learner-1", "does-not-exist") is False
        assert svc.count("learner-1") == 2

    def test_remember_empty_text_raises(self) -> None:
        svc = MemoryService(InMemoryBackend())
        with pytest.raises(MemoryStoreError):
            svc.remember("learner-1", "   ")
