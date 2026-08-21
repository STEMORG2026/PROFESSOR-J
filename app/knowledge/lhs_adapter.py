"""LearningHubSTEM Consumer Adapter — Zero-drift consumer of LHS knowledge exports."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.domain.concept import (
    ConceptEntity,
    ConceptType,
    Provenance,
    Relationship,
    ReviewStatus,
)
from app.exceptions import LHSAdapterError, LHSSchemaDriftError, EntityNotFoundError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LHSExportMeta:
    """Metadata from LHS export file."""

    export_version: str
    schema_version: str
    generated_at: str
    source: str
    entity_count: int


class LHSKnowledgeAdapter:
    """
    Consumer adapter for LearningHubSTEM knowledge exports.

    Reads `exports/knowledge.json`, validates schema version, and provides
    typed access to canonical concept entities with prerequisite traversal.
    """

    # Expected contract versions (must match exactly)
    EXPECTED_EXPORT_VERSION = "0.1"
    EXPECTED_SCHEMA_VERSION = "0.1"

    # Relationship types that indicate prerequisites
    PREREQUISITE_REL_TYPES = frozenset({
        "mathematically_requires",
        "logically_requires",
        "appears_in_law",
    })

    def __init__(self, export_path: str | Path = "LearningHubSTEM/exports/knowledge.json"):
        self.export_path = Path(export_path)
        self._cache: dict[str, ConceptEntity] = {}
        self._prerequisite_cache: dict[str, tuple[str, ...]] = {}
        self._meta: LHSExportMeta | None = None
        self._load()

    def _load(self) -> None:
        """Load and validate the LHS export file."""
        if not self.export_path.exists():
            raise LHSAdapterError(
                f"LHS export not found at {self.export_path}",
                code="LHS_EXPORT_NOT_FOUND",
            )

        try:
            with self.export_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise LHSAdapterError(
                f"Invalid JSON in LHS export: {e}",
                code="LHS_INVALID_JSON",
            )

        # Validate required top-level fields
        required_fields = {"export_version", "schema_version", "generated_at", "source", "entity_count", "entities"}
        missing = required_fields - set(data.keys())
        if missing:
            raise LHSAdapterError(
                f"LHS export missing required fields: {missing}",
                code="LHS_MISSING_FIELDS",
            )

        # Validate contract versions (zero-drift policy)
        export_version = str(data["export_version"])
        schema_version = str(data["schema_version"])

        if export_version != self.EXPECTED_EXPORT_VERSION:
            raise LHSSchemaDriftError(
                expected=self.EXPECTED_EXPORT_VERSION,
                found=export_version,
            )

        if schema_version != self.EXPECTED_SCHEMA_VERSION:
            raise LHSSchemaDriftError(
                expected=self.EXPECTED_SCHEMA_VERSION,
                found=schema_version,
            )

        self._meta = LHSExportMeta(
            export_version=export_version,
            schema_version=schema_version,
            generated_at=data["generated_at"],
            source=data["source"],
            entity_count=data["entity_count"],
        )

        # Parse and cache all entities
        self._cache.clear()
        self._prerequisite_cache.clear()

        for entity_data in data["entities"]:
            entity = self._parse_entity(entity_data)
            self._cache[entity.id] = entity

        # Build prerequisite cache
        for entity in self._cache.values():
            self._prerequisite_cache[entity.id] = entity.prerequisite_ids()

        logger.info(
            "LHS Knowledge Adapter loaded: %d entities, export v%s, schema v%s",
            len(self._cache), self._meta.export_version, self._meta.schema_version,
        )

    def _parse_entity(self, data: dict[str, Any]) -> ConceptEntity:
        """Parse raw entity dict into ConceptEntity."""
        # Parse type
        type_map = {
            "concept": ConceptType.CONCEPT,
            "law": ConceptType.LAW,
            "quantity": ConceptType.QUANTITY,
            "unit": ConceptType.UNIT,
        }
        entity_type = type_map.get(data.get("type", "concept"), ConceptType.CONCEPT)

        # Parse status
        status_map = {
            "draft": ReviewStatus.DRAFT,
            "reviewed": ReviewStatus.REVIEWED,
            "approved": ReviewStatus.APPROVED,
            "deprecated": ReviewStatus.DEPRECATED,
        }
        status = status_map.get(data.get("status", "draft"), ReviewStatus.DRAFT)

        # Parse provenance
        prov_data = data.get("provenance", {})
        provenance = Provenance(
            ai_drafted=prov_data.get("ai_drafted", True),
            source="LearningHubSTEM",
            human_reviewed=prov_data.get("human_reviewed", False),
            reviewer=prov_data.get("reviewer"),
        )

        # Parse relationships
        relationships = []
        for rel_data in data.get("relationships", []):
            relationships.append(Relationship(
                type=rel_data["type"],
                target_id=rel_data["target"],
                weight=rel_data.get("weight", 1.0),
                metadata=rel_data.get("metadata", {}),
            ))

        return ConceptEntity(
            id=data["id"],
            type=entity_type,
            name=data["name"],
            domain=data["domain"],
            definition=data.get("definition", ""),
            symbol=data.get("symbol"),
            unit=data.get("unit"),
            equation=data.get("equation"),
            common_misconceptions=tuple(data.get("common_misconceptions", [])),
            learning_objectives=tuple(data.get("learning_objectives", [])),
            real_world_applications=tuple(data.get("real_world_applications", [])),
            key_experiments=tuple(data.get("key_experiments", [])),
            relationships=tuple(relationships),
            provenance=provenance,
            status=ReviewStatus(data.get("status", "draft")),
        )

    # ── Public API ──

    def get_concept(self, entity_id: str) -> ConceptEntity | None:
        """Get a concept entity by ID. Returns None if not found."""
        return self._cache.get(entity_id)

    def get_concept_or_raise(self, entity_id: str) -> ConceptEntity:
        """Get a concept entity or raise EntityNotFoundError."""
        entity = self._cache.get(entity_id)
        if entity is None:
            raise EntityNotFoundError(entity_id)
        return entity

    def has_concept(self, entity_id: str) -> bool:
        """Check if a concept exists in the knowledge base."""
        return entity_id in self._cache

    def get_prerequisites(self, entity_id: str) -> tuple[str, ...]:
        """Get prerequisite concept IDs for an entity (cached)."""
        return self._prerequisite_cache.get(entity_id, ())

    def get_law_appearances(self, entity_id: str) -> tuple[str, ...]:
        """Get law IDs that this entity appears in."""
        entity = self._cache.get(entity_id)
        if entity is None:
            return ()
        return entity.law_appearances()

    def get_related_concepts(self, entity_id: str) -> tuple[str, ...]:
        """Get related concept IDs."""
        entity = self._cache.get(entity_id)
        if entity is None:
            return ()
        return entity.related_concepts()

    def search_concepts(self, query: str, limit: int = 10) -> list[ConceptEntity]:
        """Simple text search over concept names and definitions."""
        query_lower = query.lower()
        results = []
        for entity in self._cache.values():
            if query_lower in entity.name.lower() or query_lower in entity.definition.lower():
                results.append(entity)
                if len(results) >= limit:
                    break
        return results

    def get_all_concepts(self) -> tuple[ConceptEntity, ...]:
        """Get all cached concepts."""
        return tuple(self._cache.values())

    def get_concepts_by_domain(self, domain: str) -> tuple[ConceptEntity, ...]:
        """Get all concepts in a specific domain."""
        return tuple(e for e in self._cache.values() if e.domain == domain)

    def get_concepts_by_type(self, concept_type: ConceptType) -> tuple[ConceptEntity, ...]:
        """Get all concepts of a specific type."""
        return tuple(e for e in self._cache.values() if e.type == concept_type)

    # ── Metadata ──

    @property
    def meta(self) -> LHSExportMeta | None:
        return self._meta

    def get_stats(self) -> dict[str, Any]:
        """Get adapter statistics."""
        return {
            "entity_count": len(self._cache),
            "export_version": self._meta.export_version if self._meta else None,
            "schema_version": self._meta.schema_version if self._meta else None,
            "generated_at": self._meta.generated_at if self._meta else None,
            "source": self._meta.source if self._meta else None,
            "domains": len(set(e.domain for e in self._cache.values())),
            "concept_types": {t.value: len([e for e in self._cache.values() if e.type == t])
                              for t in ConceptType},
        }

    def reload(self) -> None:
        """Force reload of the export file (useful for hot-reload in dev)."""
        logger.info("Reloading LHS knowledge adapter...")
        self._load()


class GeneralKnowledgeAdapter:
    """
    Fallback adapter for non-grounded knowledge.

    Used when LHS has no canonical entity for a query.
    Responses are explicitly labeled as ungrounded.
    """

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}  # Simple in-memory cache

    def has_concept(self, entity_id: str) -> bool:
        """Always returns False — no canonical entities here."""
        return False

    def get_concept(self, entity_id: str) -> None:
        """Always returns None — no canonical entities."""
        return None

    def get_prerequisites(self, entity_id: str) -> tuple[str, ...]:
        """No prerequisites in general knowledge."""
        return ()

    def search_concepts(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Return empty list — no searchable concepts."""
        return []

    def get_concept_ungrounded(self, query: str) -> dict[str, Any] | None:
        """
        Generate an ungrounded response for a query.

        This is a placeholder — in production, this would call a general LLM
        with appropriate system prompt to generate a response labeled as ungrounded.
        """
        return {
            "id": f"ungrounded:{query[:50]}",
            "name": query,
            "definition": f"[UNGROUNDED] No canonical source found for '{query}'. This response is generated from general knowledge and may not be verified.",
            "grounded": False,
            "source": "general_knowledge",
            "warning": "This information is not grounded in LearningHubSTEM canonical sources. Verify independently.",
        }


# ── Factory Function ──

def create_knowledge_adapters(
    lhs_export_path: str | Path = "LearningHubSTEM/exports/knowledge.json",
) -> tuple[LHSKnowledgeAdapter, GeneralKnowledgeAdapter]:
    """
    Factory function to create both knowledge adapters.

    Returns:
        (LHSKnowledgeAdapter, GeneralKnowledgeAdapter)
    """
    lhs_adapter = LHSKnowledgeAdapter(lhs_export_path)
    general_adapter = GeneralKnowledgeAdapter()
    return lhs_adapter, general_adapter
