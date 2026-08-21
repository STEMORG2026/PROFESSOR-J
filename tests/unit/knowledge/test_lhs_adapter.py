"""Tests for LHS Knowledge Adapter."""

from __future__ import annotations

import pytest
from app.knowledge.lhs_adapter import LHSKnowledgeAdapter, GeneralKnowledgeAdapter


class TestLHSKnowledgeAdapter:
    @pytest.fixture
    def adapter(self):
        return LHSKnowledgeAdapter('/home/sajan/Projects/LearningHubSTEM/exports/knowledge.json')

    def test_load_export(self, adapter):
        assert len(adapter._cache) == 75
        assert adapter.meta.export_version == "0.1"
        assert adapter.meta.schema_version == "0.1"

    def test_get_concept(self, adapter):
        concept = adapter.get_concept("lhs:phys.force")
        assert concept is not None
        assert concept.id == "lhs:phys.force"
        assert concept.name == "Force"
        assert concept.type.value == "concept"  # Actual type in export
        assert concept.domain == "physics"
        assert "F = m" in concept.equation  # Equation format varies
        assert "newton" in concept.unit.lower()

    def test_get_concept_not_found(self, adapter):
        concept = adapter.get_concept("lhs:nonexistent")
        assert concept is None

    def test_get_concept_or_raise(self, adapter):
        concept = adapter.get_concept_or_raise("lhs:phys.force")
        assert concept.id == "lhs:phys.force"

        with pytest.raises(Exception):  # EntityNotFoundError
            adapter.get_concept_or_raise("lhs:nonexistent")

    def test_has_concept(self, adapter):
        assert adapter.has_concept("lhs:phys.force") is True
        assert adapter.has_concept("lhs:nonexistent") is False

    def test_prerequisites(self, adapter):
        prereqs = adapter.get_prerequisites("lhs:phys.force")
        assert "lhs:phys.mass" in prereqs
        assert "lhs:phys.acceleration" in prereqs
        assert "lhs:phys.vector" in prereqs

    def test_law_appearances(self, adapter):
        laws = adapter.get_law_appearances("lhs:phys.force")
        assert "lhs:phys.newtons-first-law" in laws
        assert "lhs:phys.newtons-second-law" in laws
        assert "lhs:phys.newtons-third-law" in laws

    def test_search_concepts(self, adapter):
        results = adapter.search_concepts("force", limit=5)
        assert len(results) > 0
        assert any("force" in c.name.lower() for c in results)

    def test_get_concepts_by_domain(self, adapter):
        physics = adapter.get_concepts_by_domain("physics")
        assert len(physics) == 75  # All entities are physics in this export

    def test_get_concepts_by_type(self, adapter):
        laws = adapter.get_concepts_by_type("law")
        assert len(laws) == 8
        assert all(c.type.value == "law" for c in laws)

    def test_reload(self, adapter):
        original_count = len(adapter._cache)
        adapter.reload()
        assert len(adapter._cache) == 75


class TestGeneralKnowledgeAdapter:
    def test_has_concept_false(self):
        adapter = GeneralKnowledgeAdapter()
        assert adapter.has_concept("anything") is False

    def test_get_concept_none(self):
        adapter = GeneralKnowledgeAdapter()
        assert adapter.get_concept("anything") is None

    def test_get_prerequisites_empty(self):
        adapter = GeneralKnowledgeAdapter()
        assert adapter.get_prerequisites("anything") == ()

    def test_search_concepts_empty(self):
        adapter = GeneralKnowledgeAdapter()
        assert adapter.search_concepts("query") == []

    def test_get_concept_ungrounded(self):
        adapter = GeneralKnowledgeAdapter()
        result = adapter.get_concept_ungrounded("What is gravity?")
        assert result is not None
        assert result["grounded"] is False
        assert "UNGROUNDED" in result["definition"]
        assert "general_knowledge" in result["source"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
