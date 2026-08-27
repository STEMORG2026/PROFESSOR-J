"""Concept Entity — Canonical STEM knowledge with provenance and review status."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ReviewStatus(str, Enum):
    """Review status of a canonical entity (mirrors LearningHubSTEM)."""

    DRAFT = "draft"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    DEPRECATED = "deprecated"


class ConceptType(str, Enum):
    """Type of canonical concept."""

    CONCEPT = "concept"
    LAW = "law"
    QUANTITY = "quantity"
    UNIT = "unit"


@dataclass(frozen=True, slots=True)
class Provenance:
    """Provenance information for a concept."""

    ai_drafted: bool = True
    source: str = "LearningHubSTEM"
    generated_at: datetime = field(default_factory=datetime.utcnow)
    human_reviewed: bool = False
    reviewer: str | None = None
    reviewed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def with_human_review(self, reviewer: str) -> Provenance:
        """Return new provenance with human review marked."""
        return Provenance(
            ai_drafted=self.ai_drafted,
            source=self.source,
            generated_at=self.generated_at,
            human_reviewed=True,
            reviewer=reviewer,
            reviewed_at=datetime.utcnow(),
            metadata=self.metadata,
        )


@dataclass(frozen=True, slots=True)
class Relationship:
    """Relationship between concepts."""

    type: str  # mathematically_requires, logically_requires, appears_in_law, related_to, applies_to
    target_id: str  # target concept ID (e.g., "lhs:phys.velocity")
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ConceptEntity:
    """
    Canonical STEM concept entity with full provenance and relationships.

    Immutable, serializable, zero external dependencies.
    Maps to LearningHubSTEM export schema.
    """

    # Identity
    id: str  # e.g., "lhs:phys.newtons-second-law"
    type: ConceptType
    name: str
    domain: str  # physics, chemistry, mathematics, etc.

    # Content
    definition: str
    symbol: str | None = None
    unit: str | None = None
    equation: str | None = None

    # Pedagogical
    common_misconceptions: tuple[str, ...] = field(default_factory=tuple)
    learning_objectives: tuple[str, ...] = field(default_factory=tuple)
    real_world_applications: tuple[str, ...] = field(default_factory=tuple)
    key_experiments: tuple[str, ...] = field(default_factory=tuple)

    # Relationships & Provenance
    relationships: tuple[Relationship, ...] = field(default_factory=tuple)
    provenance: Provenance = field(default_factory=Provenance)
    status: ReviewStatus = ReviewStatus.DRAFT

    # Prerequisite traversal helpers
    def prerequisite_ids(self) -> tuple[str, ...]:
        """Get all prerequisite concept IDs (mathematically_requires + logically_requires)."""
        return tuple(
            rel.target_id
            for rel in self.relationships
            if rel.type in ("mathematically_requires", "logically_requires")
        )

    def law_appearances(self) -> tuple[str, ...]:
        """Get laws this concept appears in."""
        return tuple(
            rel.target_id for rel in self.relationships if rel.type == "appears_in_law"
        )

    def related_concepts(self) -> tuple[str, ...]:
        """Get all related concept IDs."""
        return tuple(
            rel.target_id
            for rel in self.relationships
            if rel.type in ("related_to", "applies_to")
        )

    def all_dependencies(self) -> tuple[str, ...]:
        """All concept IDs this concept depends on (prerequisites + law appearances)."""
        return self.prerequisite_ids() + self.law_appearances()

    def is_grounded(self) -> bool:
        """Whether this concept has human-reviewed provenance."""
        return self.provenance.human_reviewed and self.status in (
            ReviewStatus.REVIEWED,
            ReviewStatus.APPROVED,
        )

    def citation_string(self) -> str:
        """Generate citation string for this concept."""
        review_suffix = " ✓" if self.is_grounded() else " ⚠ (AI-drafted)"
        return f"[{self.id}] {self.name}{review_suffix}"

    def to_citation_dict(self) -> dict[str, Any]:
        """Minimal dict for citation in responses."""
        return {
            "id": self.id,
            "name": self.name,
            "equation": self.equation,
            "unit": self.unit,
            "status": self.status.value,
            "reviewed": self.provenance.human_reviewed,
            "provenance": "LearningHubSTEM",
        }
