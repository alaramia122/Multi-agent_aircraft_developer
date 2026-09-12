"""Application service for loading, validating and composing standard profiles."""

from collections.abc import Iterable

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
    """Compose profiles using stable identifiers and explicit conflict detection.

    A later profile may add definitions, but it cannot silently replace a definition
    with the same identifier. This keeps profile composition deterministic and makes
    accidental semantic conflicts visible before a profile is activated.
    """

    @staticmethod
    def compose(profiles: Iterable[StandardProfile], *, id: str, version: str, name: str) -> StandardProfile:
        profiles = list(profiles)
        if not profiles:
            raise ProfileCompositionError("at least one profile is required")

        element_types = StandardProfileEngine._merge(profiles, "element_types")
        relations = StandardProfileEngine._merge(profiles, "relations")
        lifecycles = StandardProfileEngine._merge(profiles, "lifecycles")
        artifacts = StandardProfileEngine._merge(profiles, "artifacts")
        traceability = StandardProfileEngine._merge(profiles, "traceability")
        verification = StandardProfileEngine._merge(profiles, "verification")

        return StandardProfile(
            id=id,
            version=version,
            name=name,
            description=f"Composition of: {', '.join(profile.id for profile in profiles)}",
            element_types=element_types,
            relations=relations,
            lifecycles=lifecycles,
            artifacts=artifacts,
            traceability=traceability,
            verification=verification,
            metadata={"composed_from": [profile.id for profile in profiles]},
        )

    @staticmethod
    def _merge(profiles: list[StandardProfile], field: str) -> list[object]:
        merged: dict[str, object] = {}
        for profile in profiles:
            for definition in getattr(profile, field):
                existing = merged.get(definition.id)
                if existing is not None and existing != definition:
                    raise ProfileCompositionError(
                        f"conflicting {field} definition '{definition.id}'"
                    )
                merged[definition.id] = definition
        return list(merged.values())

    @staticmethod
    def validate_profile(profile: StandardProfile) -> None:
        """Run semantic checks beyond Pydantic's structural validation."""
        element_types = {item.id: item for item in profile.element_types}
        relation_pairs = {
            (relation.relation_type, source, target)
            for relation in profile.relations
            for source in relation.source_type_ids
            for target in relation.target_type_ids
        }
        for rule in profile.traceability:
            if rule.source_type_id not in element_types or rule.target_type_id not in element_types:
                raise ProfileCompositionError(f"traceability rule '{rule.id}' references unknown type")
            if (
                rule.relation_type,
                rule.source_type_id,
                rule.target_type_id,
            ) not in relation_pairs:
                raise ProfileCompositionError(
                    f"traceability rule '{rule.id}' has no matching relation definition"
                )

        for rule in profile.verification:
            if rule.element_type_id not in element_types:
                raise ProfileCompositionError(f"verification rule '{rule.id}' references unknown type")
            if rule.verification_type_id not in element_types:
                raise ProfileCompositionError(
                    f"verification rule '{rule.id}' references unknown verification type"
                )

        StandardProfileEngine._validate_unique_definition_types(profile)

    @staticmethod
    def _validate_unique_definition_types(profile: StandardProfile) -> None:
        definitions: tuple[tuple[str, list[object]], ...] = (
            ("element_types", profile.element_types),
            ("relations", profile.relations),
            ("lifecycles", profile.lifecycles),
            ("artifacts", profile.artifacts),
            ("traceability", profile.traceability),
            ("verification", profile.verification),
        )
        for name, values in definitions:
            if len({value.id for value in values}) != len(values):
                raise ProfileCompositionError(f"duplicate {name} definitions")


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
