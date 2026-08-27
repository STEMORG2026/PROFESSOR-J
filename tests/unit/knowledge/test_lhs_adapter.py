"""Tests for LHS Knowledge Adapter.

Two tiers of testing:

1. **Deterministic unit tests** run against a stable, checked-in fixture
   (`tests/fixtures/lhs_knowledge_fixture.json`). Assertions pin exact counts
   and relationships of that fixture, so parsing logic is fully reproducible
   and CI-portable.

2. **Structural contract test** runs against the real LearningHubSTEM export
   when it is present on the machine, and is skipped otherwise. It validates
   only structural invariants that must always hold (required fields, count
   agreement, unique IDs, resolvable prerequisite targets) — never volatile
   entity counts, which legitimately change as LearningHubSTEM grows.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.concept import ConceptType, ReviewStatus
from app.knowledge.lhs_adapter import GeneralKnowledgeAdapter, LHSKnowledgeAdapter

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "lhs_knowledge_fixture.json"

# Known, deterministic facts about the fixture (update only if the fixture changes).
FIXTURE_COUNTS = {
    "total": 9,
    "concept": 3,  # force, animal-cell, scientific-practice.variable
    "quantity": 2,  # mass, acceleration
    "law": 3,  # newtons-1st, newtons-2nd, hooke
    "equation": 1,  # chem.balanced-equation (parsed as CONCEPT by current type_map)
    "unit": 0,
    "physics": 5,
    "reviewed": 3,  # mass, newtons-1st, newtons-2nd
}


def _find_real_export() -> Path | None:
    """Locate the real LearningHubSTEM export if present on this machine."""
    candidates = [
        Path(__file__).resolve().parents[2] / "LearningHubSTEM" / "exports" / "knowledge.json",
        Path("/home/sajan/Projects/LearningHubSTEM/exports/knowledge.json"),
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


class TestLHSKnowledgeAdapter:
    @pytest.fixture
    def adapter(self) -> LHSKnowledgeAdapter:
        return LHSKnowledgeAdapter(FIXTURE)

    def test_load_export_meta(self, adapter: LHSKnowledgeAdapter) -> None:
        assert adapter.meta is not None
        assert adapter.meta.export_version == "0.1"
        assert adapter.meta.schema_version == "0.1"
        assert adapter.meta.entity_count == FIXTURE_COUNTS["total"]
        assert adapter.meta.source == "content/"

    def test_load_export_parses_all_entities(self, adapter: LHSKnowledgeAdapter) -> None:
        assert len(adapter.get_all_concepts()) == FIXTURE_COUNTS["total"]

    def test_get_concept_grounded(self, adapter: LHSKnowledgeAdapter) -> None:
        concept = adapter.get_concept("lhs:phys.force")
        assert concept is not None
        assert concept.id == "lhs:phys.force"
        assert concept.name == "Force"
        assert concept.domain == "physics"
        assert concept.is_grounded()  # human_reviewed + approved status

    def test_get_concept_draft_not_grounded(self, adapter: LHSKnowledgeAdapter) -> None:
        accel = adapter.get_concept("lhs:phys.acceleration")
        assert accel is not None
        assert accel.status == ReviewStatus.DRAFT
        assert not accel.is_grounded()

    def test_get_concept_not_found(self, adapter: LHSKnowledgeAdapter) -> None:
        assert adapter.get_concept("lhs:nonexistent") is None
        assert adapter.has_concept("lhs:nonexistent") is False

    def test_get_concept_or_raise(self, adapter: LHSKnowledgeAdapter) -> None:
        from app.exceptions import EntityNotFoundError

        assert adapter.get_concept_or_raise("lhs:phys.force").id == "lhs:phys.force"
        with pytest.raises(EntityNotFoundError):
            adapter.get_concept_or_raise("lhs:nonexistent")

    def test_prerequisites(self, adapter: LHSKnowledgeAdapter) -> None:
        prereqs = adapter.get_prerequisites("lhs:phys.force")
        assert "lhs:phys.mass" in prereqs
        assert "lhs:phys.acceleration" in prereqs

    def test_law_appearances(self, adapter: LHSKnowledgeAdapter) -> None:
        laws = adapter.get_law_appearances("lhs:phys.force")
        assert "lhs:phys.newtons-first-law" in laws
        assert "lhs:phys.newtons-second-law" in laws

    def test_search_concepts(self, adapter: LHSKnowledgeAdapter) -> None:
        results = adapter.search_concepts("force", limit=5)
        assert results
        assert any("force" in c.name.lower() for c in results)

    def test_get_concepts_by_domain(self, adapter: LHSKnowledgeAdapter) -> None:
        physics = adapter.get_concepts_by_domain("physics")
        assert len(physics) == FIXTURE_COUNTS["physics"]

    def test_get_concepts_by_type(self, adapter: LHSKnowledgeAdapter) -> None:
        laws = adapter.get_concepts_by_type(ConceptType.LAW)
        assert len(laws) == FIXTURE_COUNTS["law"]
        assert all(c.type == ConceptType.LAW for c in laws)

    def test_get_stats(self, adapter: LHSKnowledgeAdapter) -> None:
        stats = adapter.get_stats()
        assert stats["entity_count"] == FIXTURE_COUNTS["total"]
        assert stats["export_version"] == "0.1"
        assert stats["domains"] == 5  # physics, chemistry, biology, engineering, scientific-practice

    def test_reload_idempotent(self, adapter: LHSKnowledgeAdapter) -> None:
        before = len(adapter.get_all_concepts())
        adapter.reload()
        assert len(adapter.get_all_concepts()) == before == FIXTURE_COUNTS["total"]


class TestGeneralKnowledgeAdapter:
    def test_has_concept_false(self) -> None:
        assert GeneralKnowledgeAdapter().has_concept("anything") is False

    def test_get_concept_none(self) -> None:
        assert GeneralKnowledgeAdapter().get_concept("anything") is None

    def test_get_prerequisites_empty(self) -> None:
        assert GeneralKnowledgeAdapter().get_prerequisites("anything") == ()

    def test_search_concepts_empty(self) -> None:
        assert GeneralKnowledgeAdapter().search_concepts("query") == []

    def test_get_concept_ungrounded(self) -> None:
        result = GeneralKnowledgeAdapter().get_concept_ungrounded("What is gravity?")
        assert result is not None
        assert result["grounded"] is False
        assert "UNGROUNDED" in result["definition"]
        assert "general_knowledge" in result["source"]


class TestLHSSchemaContract:
    """Zero-drift structural contract against the real LHS export (skipped if absent)."""

    @pytest.fixture
    def real_export_path(self) -> Path | None:
        return _find_real_export()

    def test_real_export_structure(self, real_export_path: Path | None) -> None:
        if real_export_path is None:
            pytest.skip("Real LearningHubSTEM export not present; skipping contract test.")
        adapter = LHSKnowledgeAdapter(real_export_path)
        assert adapter.meta is not None
        # Required top-level contract fields must be present (verified by adapter load).
        assert adapter.meta.entity_count == len(adapter.get_all_concepts())

    def test_real_export_ids_unique(self, real_export_path: Path | None) -> None:
        if real_export_path is None:
            pytest.skip("Real LearningHubSTEM export not present; skipping contract test.")
        adapter = LHSKnowledgeAdapter(real_export_path)
        ids = [c.id for c in adapter.get_all_concepts()]
        assert len(ids) == len(set(ids)), "Entity IDs must be unique in the export"

    def test_real_export_prerequisites_resolve(
        self, real_export_path: Path | None
    ) -> None:
        if real_export_path is None:
            pytest.skip("Real LearningHubSTEM export not present; skipping contract test.")
        adapter = LHSKnowledgeAdapter(real_export_path)
        available = {c.id for c in adapter.get_all_concepts()}
        dangling: set[str] = set()
        for concept in adapter.get_all_concepts():
            for prereq in concept.prerequisite_ids():
                if prereq not in available:
                    dangling.add(prereq)
        assert not dangling, f"Prerequisites point at missing entities: {sorted(dangling)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
