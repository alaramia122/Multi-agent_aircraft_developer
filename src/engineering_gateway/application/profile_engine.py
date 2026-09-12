"""Application service for loading, validating and composing standard profiles."""

from collections.abc import Iterable
from typing import Any

from engineering_gateway.domain.profiles import (
    ArtifactRequirement,
    ElementTypeDefinition,
    LifecycleDefinition,
    RelationDefinition,
    StandardProfile,
    TraceabilityRule,
    VerificationRule,
)


class ProfileCompositionError(ValueError):
    """Raised when profiles cannot be composed deterministically."""


class StandardProfileEngine:
    """Validate and compose declarative Standard Profiles.

    The engine is deliberately independent of persistence and of any particular
    engineering standard. Profiles are immutable versioned definitions; composition
    is deterministic and conflicting definitions are never silently overridden.
    """

    _DEFINITION_FIELDS = (
        "element_types",
        "relations",
        "lifecycles",
        "artifacts",
        "traceability",
        "verification",
    )

    @classmethod
    def compose(
        cls,
        profiles: Iterable[StandardProfile],
        *,
        id: str,
        version: str,
        name: str,
    ) -> StandardProfile:
        profiles = list(profiles)
        if not profiles:
            raise ProfileCompositionError("at least one profile is required")
        for profile in profiles:
            cls.validate_profile(profile)

        return StandardProfile(
            id=id,
            version=version,
            name=name,
            description=f"Composition of: {', '.join(f'{p.id}@{p.version}' for p in profiles)}",
            element_types=cls._merge(profiles, "element_types"),
            relations=cls._merge(profiles, "relations"),
            lifecycles=cls._merge(profiles, "lifecycles"),
            artifacts=cls._merge(profiles, "artifacts"),
            traceability=cls._merge(profiles, "traceability"),
            verification=cls._merge(profiles, "verification"),
            metadata={
                "composed_from": [f"{profile.id}@{profile.version}" for profile in profiles],
            },
        )

    @staticmethod
    def _merge(profiles: list[StandardProfile], field: str) -> list[Any]:
        merged: dict[str, Any] = {}
        for profile in profiles:
            for definition in getattr(profile, field):
                existing = merged.get(definition.id)
                if existing is not None and existing != definition:
                    raise ProfileCompositionError(
                        f"conflicting {field} definition '{definition.id}'"
                    )
                merged[definition.id] = definition
        return list(merged.values())

    @classmethod
    def validate_profile(cls, profile: StandardProfile) -> None:
        """Run semantic validation beyond Pydantic structural checks."""
        cls._validate_unique_definition_types(profile)
        element_types = {item.id: item for item in profile.element_types}
        cls._validate_relations(profile, element_types)
        cls._validate_lifecycles(profile, element_types)
        cls._validate_artifacts(profile, element_types)
        cls._validate_traceability(profile, element_types)
        cls._validate_verification(profile, element_types)

    @classmethod
    def _validate_relations(
        cls, profile: StandardProfile, element_types: dict[str, ElementTypeDefinition]
    ) -> None:
        for relation in profile.relations:
            if not relation.source_type_ids or not relation.target_type_ids:
                raise ProfileCompositionError(
                    f"relation '{relation.id}' must define source and target types"
                )
            unknown = (set(relation.source_type_ids) | set(relation.target_type_ids)) - set(element_types)
            if unknown:
                raise ProfileCompositionError(
                    f"relation '{relation.id}' references unknown types: {sorted(unknown)}"
                )

    @classmethod
    def _validate_lifecycles(
        cls, profile: StandardProfile, element_types: dict[str, ElementTypeDefinition]
    ) -> None:
        lifecycle_types: set[str] = set()
        for lifecycle in profile.lifecycles:
            if lifecycle.element_type_id not in element_types:
                raise ProfileCompositionError(
                    f"lifecycle '{lifecycle.id}' references unknown element type"
                )
            if lifecycle.element_type_id in lifecycle_types:
                raise ProfileCompositionError(
                    f"multiple lifecycle definitions for element type '{lifecycle.element_type_id}'"
                )
            lifecycle_types.add(lifecycle.element_type_id)
            states = set(lifecycle.states)
            if not states:
                raise ProfileCompositionError(f"lifecycle '{lifecycle.id}' has no states")
            for source, targets in lifecycle.transitions.items():
                if source not in states:
                    raise ProfileCompositionError(
                        f"lifecycle '{lifecycle.id}' has unknown source state '{source}'"
                    )
                if len(targets) != len(set(targets)):
                    raise ProfileCompositionError(
                        f"lifecycle '{lifecycle.id}' has duplicate transition targets for '{source}'"
                    )

    @staticmethod
    def _validate_artifacts(
        profile: StandardProfile, element_types: dict[str, ElementTypeDefinition]
    ) -> None:
        for artifact in profile.artifacts:
            if artifact.element_type_id not in element_types:
                raise ProfileCompositionError(
                    f"artifact '{artifact.id}' references unknown element type"
                )
            if not artifact.artifact_type.strip():
                raise ProfileCompositionError(f"artifact '{artifact.id}' has an empty artifact type")

    @classmethod
    def _validate_traceability(
        cls, profile: StandardProfile, element_types: dict[str, ElementTypeDefinition]
    ) -> None:
        relation_pairs = {
            (relation.relation_type, source, target)
            for relation in profile.relations
            for source in relation.source_type_ids
            for target in relation.target_type_ids
        }
        for rule in profile.traceability:
            if rule.source_type_id not in element_types or rule.target_type_id not in element_types:
                raise ProfileCompositionError(
                    f"traceability rule '{rule.id}' references unknown type"
                )
            if (
                rule.relation_type,
                rule.source_type_id,
                rule.target_type_id,
            ) not in relation_pairs:
                raise ProfileCompositionError(
                    f"traceability rule '{rule.id}' has no matching relation definition"
                )

    @classmethod
    def _validate_verification(
        cls, profile: StandardProfile, element_types: dict[str, ElementTypeDefinition]
    ) -> None:
        relation_pairs = {
            (relation.relation_type, source, target)
            for relation in profile.relations
            for source in relation.source_type_ids
            for target in relation.target_type_ids
        }
        for rule in profile.verification:
            if rule.element_type_id not in element_types:
                raise ProfileCompositionError(
                    f"verification rule '{rule.id}' references unknown type"
                )
            if rule.verification_type_id not in element_types:
                raise ProfileCompositionError(
                    f"verification rule '{rule.id}' references unknown verification type"
                )
            if (
                rule.required_relation_type,
                rule.element_type_id,
                rule.verification_type_id,
            ) not in relation_pairs:
                raise ProfileCompositionError(
                    f"verification rule '{rule.id}' has no matching verification relation definition"
                )

    @classmethod
    def _validate_unique_definition_types(cls, profile: StandardProfile) -> None:
        for field in cls._DEFINITION_FIELDS:
            values = getattr(profile, field)
            if len({value.id for value in values}) != len(values):
                raise ProfileCompositionError(f"duplicate {field} definitions")


__all__ = [
    "ArtifactRequirement",
    "ElementTypeDefinition",
    "LifecycleDefinition",
    "ProfileCompositionError",
    "RelationDefinition",
    "StandardProfile",
    "StandardProfileEngine",
    "TraceabilityRule",
    "VerificationRule",
]
