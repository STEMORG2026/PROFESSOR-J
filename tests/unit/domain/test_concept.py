"""Tests for domain concept entities."""

from __future__ import annotations

import pytest
from app.domain.concept import (
    ConceptEntity,
    ConceptType,
    ReviewStatus,
    Provenance,
    Relationship,
)


class TestProvenance:
    def test_default_provenance(self):
        prov = Provenance()
        assert prov.ai_drafted is True
        assert prov.human_reviewed is False
        assert prov.source == "LearningHubSTEM"

    def test_with_human_review(self):
        prov = Provenance()
        reviewed = prov.with_human_review("Dr. Smith")
        assert reviewed.human_reviewed is True
        assert reviewed.reviewer == "Dr. Smith"
        assert reviewed.reviewed_at is not None
        # Original unchanged
        assert prov.human_reviewed is False

    def test_immutable(self):
        prov = Provenance()
        with pytest.raises(AttributeError):  # frozen dataclass
            prov.ai_drafted = False  # type: ignore


class TestRelationship:
    def test_relationship_creation(self):
        rel = Relationship(
            type="mathematically_requires", target_id="lhs:phys.velocity"
        )
        assert rel.type == "mathematically_requires"
        assert rel.target_id == "lhs:phys.velocity"
        assert rel.weight == 1.0


class TestConceptEntity:
    def test_basic_creation(self):
        concept = ConceptEntity(
            id="lhs:phys.force",
            type=ConceptType.LAW,
            name="Force",
            domain="physics",
            definition="Force is a push or pull",
            equation="F = m * a",
            unit="Newton (N)",
        )
        assert concept.id == "lhs:phys.force"
        assert concept.type == ConceptType.LAW
        assert concept.status == ReviewStatus.DRAFT
        assert concept.provenance.ai_drafted is True

    def test_related_concepts(self):
        concept = ConceptEntity(
            id="lhs:phys.force",
            type=ConceptType.CONCEPT,
            name="Force",
            domain="physics",
            definition="Force definition",
            relationships=(
                Relationship(type="related_to", target_id="lhs:phys.energy"),
                Relationship(type="applies_to", target_id="lhs:phys.pressure"),
                Relationship(type="mathematically_requires", target_id="lhs:phys.mass"),
            ),
        )
        related = concept.related_concepts()
        assert "lhs:phys.energy" in related
        assert "lhs:phys.pressure" in related
        assert "lhs:phys.mass" not in related

    def test_prerequisite_ids(self):
        concept = ConceptEntity(
            id="lhs:phys.force",
            type=ConceptType.LAW,
            name="Force",
            domain="physics",
            definition="Force definition",
            relationships=(
                Relationship(type="mathematically_requires", target_id="lhs:phys.mass"),
                Relationship(
                    type="logically_requires", target_id="lhs:phys.acceleration"
                ),
                Relationship(
                    type="appears_in_law", target_id="lhs:phys.newtons-second-law"
                ),
                Relationship(type="related_to", target_id="lhs:phys.energy"),
            ),
        )
        prereqs = concept.prerequisite_ids()
        assert "lhs:phys.mass" in prereqs
        assert "lhs:phys.acceleration" in prereqs
        assert len(prereqs) == 2

    def test_law_appearances(self):
        concept = ConceptEntity(
            id="lhs:phys.mass",
            type=ConceptType.QUANTITY,
            name="Mass",
            domain="physics",
            definition="Mass definition",
            relationships=(
                Relationship(
                    type="appears_in_law", target_id="lhs:phys.newtons-second-law"
                ),
                Relationship(
                    type="appears_in_law",
                    target_id="lhs:phys.newtons-law-of-gravitation",
                ),
            ),
        )
        laws = concept.law_appearances()
        assert "lhs:phys.newtons-second-law" in laws
        assert "lhs:phys.newtons-law-of-gravitation" in laws

    def test_all_dependencies(self):
        concept = ConceptEntity(
            id="lhs:phys.force",
            type=ConceptType.LAW,
            name="Force",
            domain="physics",
            definition="Force",
            relationships=(
                Relationship(type="mathematically_requires", target_id="lhs:phys.mass"),
                Relationship(
                    type="logically_requires", target_id="lhs:phys.acceleration"
                ),
                Relationship(
                    type="appears_in_law", target_id="lhs:phys.newtons-second-law"
                ),
            ),
        )
        deps = concept.all_dependencies()
        assert len(deps) == 3

    def test_citation_dict(self):
        concept = ConceptEntity(
            id="lhs:phys.force",
            type=ConceptType.LAW,
            name="Force",
            domain="physics",
            definition="Force",
            equation="F = m * a",
            unit="Newton (N)",
        )
        citation = concept.to_citation_dict()
        assert citation["id"] == "lhs:phys.force"
        assert citation["name"] == "Force"
        assert citation["equation"] == "F = m * a"
        assert citation["unit"] == "Newton (N)"
        assert citation["status"] == "draft"
        assert citation["reviewed"] is False
        assert citation["provenance"] == "LearningHubSTEM"

    def test_is_grounded(self):
        concept = ConceptEntity(
            id="lhs:phys.force",
            type=ConceptType.LAW,
            name="Force",
            domain="physics",
            definition="Force",
        )
        assert concept.is_grounded() is False
        # With human review
        reviewed_prov = Provenance().with_human_review("Dr. Smith")
        reviewed_concept = ConceptEntity(
            id="lhs:phys.force",
            type=ConceptType.LAW,
            name="Force",
            domain="physics",
            definition="Force",
            provenance=reviewed_prov,
            status=ReviewStatus.REVIEWED,
        )
        assert reviewed_concept.is_grounded() is True

    def test_citation_string(self):
        concept = ConceptEntity(
            id="lhs:phys.force",
            type=ConceptType.LAW,
            name="Force",
            domain="physics",
            definition="Force",
        )
        citation = concept.citation_string()
        assert "lhs:phys.force" in citation
        assert "Force" in citation
        assert "⚠" in citation  # AI-drafted marker


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
