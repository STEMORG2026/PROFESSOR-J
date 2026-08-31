"""Generic Game State Schema Evolution & Migration Engine.

Enables the GameDev capability to reason about state transitions across schema versions:
OLD STATE -> State Schema Diff -> NEW STATE -> Migration -> Regression Verification.

Invariants:
- 100% generic; zero coupling to any specific game rules or titles.
- Preserves backward compatibility when migrating older match states.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.domain.gamedev import (
    StateFieldDiff,
    StateMigrationResult,
    StateSchemaDiff,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class GameStateSchema:
    """Specification of a game state version and its field descriptors."""

    version: int
    fields: dict[str, dict[str, Any]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def has_field(self, name: str) -> bool:
        return name in self.fields


class GameStateEvolutionEngine:
    """Generic engine for calculating state schema diffs and executing migrations."""

    @staticmethod
    def compute_diff(
        old_schema: GameStateSchema,
        new_schema: GameStateSchema,
        renames: dict[str, str] | None = None,
    ) -> StateSchemaDiff:
        """Compute structural differences between two state schema definitions."""
        rename_map = renames or {}
        added: list[StateFieldDiff] = []
        removed: list[StateFieldDiff] = []
        renamed: list[StateFieldDiff] = []
        modified: list[StateFieldDiff] = []

        old_names = set(old_schema.fields.keys())
        new_names = set(new_schema.fields.keys())

        # Check renames first
        for old_k, new_k in rename_map.items():
            if old_k in old_names and new_k in new_names:
                renamed.append(
                    StateFieldDiff(
                        field_name=new_k,
                        change_type="renamed",
                        old_name=old_k,
                        old_type=old_schema.fields[old_k].get("type"),
                        new_type=new_schema.fields[new_k].get("type"),
                        default_value=new_schema.fields[new_k].get("default"),
                    )
                )

        renamed_old = {r.old_name for r in renamed if r.old_name}
        renamed_new = {r.field_name for r in renamed}

        # Added fields
        for name in new_names - old_names - renamed_new:
            spec = new_schema.fields[name]
            added.append(
                StateFieldDiff(
                    field_name=name,
                    change_type="added",
                    new_type=spec.get("type"),
                    default_value=spec.get("default"),
                )
            )

        # Removed fields
        for name in old_names - new_names - renamed_old:
            spec = old_schema.fields[name]
            removed.append(
                StateFieldDiff(
                    field_name=name,
                    change_type="removed",
                    old_type=spec.get("type"),
                )
            )

        # Modified fields (type or default changed)
        for name in old_names & new_names:
            old_spec = old_schema.fields[name]
            new_spec = new_schema.fields[name]
            if old_spec.get("type") != new_spec.get("type") or old_spec.get(
                "default"
            ) != new_spec.get("default"):
                modified.append(
                    StateFieldDiff(
                        field_name=name,
                        change_type="type_changed"
                        if old_spec.get("type") != new_spec.get("type")
                        else "default_changed",
                        old_type=old_spec.get("type"),
                        new_type=new_spec.get("type"),
                        default_value=new_spec.get("default"),
                    )
                )

        requires_migration = bool(added or removed or renamed or modified)

        return StateSchemaDiff(
            from_version=old_schema.version,
            to_version=new_schema.version,
            added_fields=tuple(added),
            removed_fields=tuple(removed),
            renamed_fields=tuple(renamed),
            modified_fields=tuple(modified),
            requires_migration=requires_migration,
        )

    @staticmethod
    def migrate_state(
        state_dict: dict[str, Any],
        diff: StateSchemaDiff,
    ) -> StateMigrationResult:
        """Migrate a raw state dictionary according to a computed StateSchemaDiff."""
        migrated = dict(state_dict)
        steps: list[str] = []

        try:
            # 1. Apply renames
            for r in diff.renamed_fields:
                if r.old_name and r.old_name in migrated:
                    migrated[r.field_name] = migrated.pop(r.old_name)
                    steps.append(f"Renamed '{r.old_name}' -> '{r.field_name}'")
                elif r.field_name not in migrated:
                    migrated[r.field_name] = r.default_value
                    steps.append(f"Initialized renamed field '{r.field_name}' with default")

            # 2. Add new fields with defaults
            for a in diff.added_fields:
                if a.field_name not in migrated:
                    migrated[a.field_name] = (
                        a.default_value() if callable(a.default_value) else a.default_value
                    )
                    steps.append(f"Added field '{a.field_name}' with default")

            # 3. Remove deprecated fields
            for rm in diff.removed_fields:
                if rm.field_name in migrated:
                    migrated.pop(rm.field_name, None)
                    steps.append(f"Removed deprecated field '{rm.field_name}'")

            # 4. Set new schema version
            migrated["schema_version"] = diff.to_version
            steps.append(f"Updated schema_version to {diff.to_version}")

            return StateMigrationResult(
                success=True,
                from_version=diff.from_version,
                to_version=diff.to_version,
                migrated_state=migrated,
                applied_steps=tuple(steps),
            )
        except Exception as e:
            return StateMigrationResult(
                success=False,
                from_version=diff.from_version,
                to_version=diff.to_version,
                migrated_state=state_dict,
                applied_steps=tuple(steps),
                error=f"Migration failed: {e}",
            )

    def upgrade_to_target(
        self,
        state_dict: dict[str, Any],
        target_schema: GameStateSchema,
    ) -> StateMigrationResult:
        """Convenience method to upgrade an arbitrary state dict to a target schema version."""
        current_version = state_dict.get("schema_version", 1)
        if current_version == target_schema.version:
            return StateMigrationResult(
                success=True,
                from_version=current_version,
                to_version=target_schema.version,
                migrated_state=state_dict,
                applied_steps=("State is already at target schema version",),
            )

        # Build synthetic old schema
        inferred_old_fields: dict[str, dict[str, Any]] = {
            k: {"type": type(v).__name__} for k, v in state_dict.items() if k != "schema_version"
        }
        old_schema = GameStateSchema(version=current_version, fields=inferred_old_fields)
        diff = self.compute_diff(old_schema, target_schema)
        return self.migrate_state(state_dict, diff)


__all__ = ["GameStateSchema", "GameStateEvolutionEngine"]
