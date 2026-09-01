"""Tests for the JARVIS-parity memory layer (schema, ranking, hybrid, store, manager, facts)."""

from __future__ import annotations

from pathlib import Path

from app.memory import (
    BEHAVIOR_DELETE,
    BEHAVIOR_IGNORE,
    BEHAVIOR_REPLACE,
)
from app.memory.fact_extractor import extract_facts
from app.memory.hybrid import HybridRetriever, KeywordRetriever
from app.memory.manager import MemoryManager
from app.memory.ranking import MemoryRanker, RankingWeights
from app.memory.schema import Memory
from app.memory.service import MemoryService
from app.memory.store import MemoryStore
from app.utils.text import STOP_WORDS, extract_keywords


# ── schema ────────────────────────────────────────────────────────────────
class TestSchema:
    def test_memory_roundtrip_v2(self) -> None:
        m = Memory(category="preference", memory_type="like", value="physics")
        data = m.to_dict()
        restored = Memory.from_dict(data)
        assert restored.category == "preference"
        assert restored.memory_type == "like"
        assert restored.id == m.id
        assert restored.created_at == m.created_at

    def test_memory_from_dict_tolerates_v1(self) -> None:
        # v1 shape had a single "timestamp" field.
        restored = Memory.from_dict(
            {"category": "identity", "type": "name", "value": "Sajan", "timestamp": 123.0}
        )
        assert restored.created_at == 123.0
        assert restored.updated_at == 123.0

    def test_touch_increments_access_count_and_recency(self) -> None:
        m = Memory(category="c", memory_type="t", value="v")
        before = m.access_count
        m.touch()
        assert m.access_count == before + 1
        assert m.last_used >= m.created_at

    def test_format_for_prompt(self) -> None:
        m = Memory(category="identity", memory_type="name", value="Sajan")
        assert m.format_for_prompt() == "- [identity] name: Sajan"


# ── text util ─────────────────────────────────────────────────────────────
class TestTextUtil:
    def test_extract_keywords_strips_stopwords_and_punct(self) -> None:
        assert extract_keywords("I really prefer Physics, it's great!") == {
            "really",
            "prefer",
            "physics",
            "great",
        }

    def test_stop_words_is_frozen(self) -> None:
        assert isinstance(STOP_WORDS, frozenset)


# ── ranking ───────────────────────────────────────────────────────────────
class TestRanking:
    def _mk(self, value: str, importance: float = 0.5) -> Memory:
        return Memory(category="general", memory_type="fact", value=value, importance=importance)

    def test_relevance_beats_irrelevance(self) -> None:
        ranker = MemoryRanker()
        match = self._mk("python programming language")
        nomatch = self._mk("baking bread recipes")
        results = ranker.rank([nomatch, match], query="python", limit=2)
        assert results[0].memory is match

    def test_recency_boosts_recent(self) -> None:
        import time

        ranker = MemoryRanker(recency_half_life_days=1.0)
        old = self._mk("python")
        old.last_used = time.time() - 10 * 24 * 60 * 60  # 10 days ago
        new = self._mk("python")
        new.last_used = time.time()  # now
        results = ranker.rank([old, new], query="python", limit=2)
        assert results[0].memory is new

    def test_weights_are_interpretable(self) -> None:
        assert (
            abs(
                RankingWeights().relevance
                + RankingWeights().importance
                + RankingWeights().frequency
                + RankingWeights().recency
                + RankingWeights().confidence
                - 1.0
            )
            < 1e-6
        )

    def test_importance_included_in_score(self) -> None:
        ranker = MemoryRanker(weights=RankingWeights(importance=1.0, relevance=0.0))
        low = self._mk("alpha", importance=0.2)
        high = self._mk("alpha", importance=0.9)
        results = ranker.rank([low, high], query="", limit=2)
        assert results[0].memory is high


# ── hybrid retrieval ─────────────────────────────────────────────────────
class TestHybrid:
    def test_keyword_finds_exact_and_orders_by_overlap(self) -> None:
        retriever = KeywordRetriever()
        retriever.on_index_rebuilt(
            [
                Memory(category="g", memory_type="t", value="force mass"),
                Memory(category="g", memory_type="t", value="force"),
                Memory(category="g", memory_type="t", value="unrelated"),
            ]
        )
        hits = retriever.find_candidates("force mass", limit=2)
        assert hits[0].value == "force mass"
        assert len(hits) == 2

    def test_hybrid_retriever_dedupes_by_id(self) -> None:
        kw = KeywordRetriever()
        kw.on_index_rebuilt([Memory(id="x", category="g", memory_type="t", value="python")])
        vector = KeywordRetriever()  # stand-in for a dense retriever
        vector.on_index_rebuilt([Memory(id="x", category="g", memory_type="t", value="python")])
        hybrid = HybridRetriever(keyword=kw, vector=vector)
        hits = hybrid.find_candidates("python")
        assert len(hits) == 1  # deduped by id
        assert hits[0].id == "x"

    def test_hybrid_handles_no_vector(self) -> None:
        kw = KeywordRetriever()
        kw.on_index_rebuilt([Memory(category="g", memory_type="t", value="python")])
        hybrid = HybridRetriever(keyword=kw)  # no dense leg
        assert any("python" in h.value for h in hybrid.find_candidates("python"))


# ── store ────────────────────────────────────────────────────────────────
class TestStore:
    def test_persists_and_reloads(self, tmp_path: Path) -> None:
        path = tmp_path / "mem.json"
        store = MemoryStore(path)
        store.add(Memory(category="c", memory_type="t", value="v1"))
        store.save()
        reloaded = MemoryStore(path)
        assert reloaded.count() == 1
        assert reloaded.get_all()[0].value == "v1"

    def test_update_fields_skips_invalid(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "m.json")
        m = store.add(Memory(category="c", memory_type="t", value="v", confidence=0.5))
        store.update_fields(m.id, {"confidence": "banana"})  # invalid, skipped
        first = store.get_by_id(m.id)
        assert first is not None and first.confidence == 0.5
        store.update_fields(m.id, {"value": "new"})
        second = store.get_by_id(m.id)
        assert second is not None and second.value == "new"

    def test_update_immutable_field_rejected(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "m.json")
        m = store.add(Memory(category="c", memory_type="t", value="v"))
        store.update_fields(m.id, {"id": "hijack"})  # immutable, skipped
        result = store.get_by_id(m.id)
        assert result is not None and result.id == m.id

    def test_corrupt_file_quarantined(self, tmp_path: Path) -> None:
        path = tmp_path / "m.json"
        path.write_text("{ not valid json", encoding="utf-8")
        store = MemoryStore(path)
        assert store.count() == 0


# ── manager behaviors ────────────────────────────────────────────────────
class TestManager:
    def test_append_store_and_query(self) -> None:
        mgr = MemoryManager()
        mgr.store({"category": "preference", "type": "like", "value": "python"})
        results = mgr.retrieve("python", limit=5)
        assert results and results[0].memory.value == "python"

    def test_replace_updates_matching(self) -> None:
        mgr = MemoryManager()
        mgr.store({"category": "identity", "type": "name", "value": "old"})
        mgr.store(
            {"category": "identity", "type": "name", "value": "new", "behavior": BEHAVIOR_REPLACE}
        )
        matches = mgr.get_by_type("identity", "name")
        assert len(matches) == 1
        assert matches[0].value == "new"

    def test_ignore_returns_none(self) -> None:
        mgr = MemoryManager()
        assert (
            mgr.store({"category": "c", "type": "t", "value": "x", "behavior": BEHAVIOR_IGNORE})
            is None
        )
        assert mgr.count() == 0

    def test_delete_by_type(self) -> None:
        mgr = MemoryManager()
        mgr.store({"category": "c", "type": "t", "value": "a"})
        mgr.store({"category": "c", "type": "t", "value": "b", "behavior": BEHAVIOR_DELETE})
        assert mgr.count() == 0

    def test_merge_appends_value(self) -> None:
        mgr = MemoryManager()
        stored = mgr.store({"category": "c", "type": "t", "value": "alpha"})
        assert stored is not None
        updated = mgr.merge(stored.id, {"value": "beta"})
        assert updated is not None and "alpha" in updated.value and "beta" in updated.value

    def test_lifecycle_callbacks_fire(self) -> None:
        mgr = MemoryManager()
        events: list[str] = []
        mgr.on_store(lambda _m: events.append("store"))
        mgr.on_delete(lambda _m: events.append("delete"))
        stored = mgr.store({"category": "c", "type": "t", "value": "v"})
        assert stored is not None
        mgr.delete(stored.id)
        assert events == ["store", "delete"]


# ── fact extraction ──────────────────────────────────────────────────────
class TestFactExtraction:
    def test_extracts_preference(self) -> None:
        facts = extract_facts("I like physics and I enjoy coding.")
        assert any(f["category"] == "preference" and f["type"] == "like" for f in facts)

    def test_extracts_name(self) -> None:
        facts = extract_facts("My name is Sajan and I am a developer.")
        assert any(f["category"] == "identity" and f["type"] == "name" for f in facts)

    def test_no_facts_on_plain_statement(self) -> None:
        assert extract_facts("What is the capital of France?") == []


# ── enriched service façade ──────────────────────────────────────────────
class TestServiceFacade:
    def test_store_memory_and_search(self) -> None:
        svc = MemoryService()
        svc.store_memory("like", "prefers python", category="preference")
        hits = svc.search_memories("what do they prefer python", limit=3)
        assert hits and hits[0]["value"] == "prefers python"

    def test_extract_facts_stores(self) -> None:
        svc = MemoryService()
        stored = svc.extract_facts("I love mathematics.")
        assert stored  # at least one preference fact stored
        assert svc.list_memories()

    def test_get_by_type(self) -> None:
        svc = MemoryService()
        svc.store_memory("name", "Sajan", category="identity", behavior=BEHAVIOR_REPLACE)
        assert svc.get_by_type("identity", "name")
