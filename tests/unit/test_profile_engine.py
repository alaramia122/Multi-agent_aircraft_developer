from engineering_gateway.application.profile_engine import (
    ProfileCompositionError,
    StandardProfileEngine,
)
from engineering_gateway.domain.models import ElementKind, RelationType
from engineering_gateway.domain.profiles import (
    AttributeDefinition,
    AttributeType,
    ElementTypeDefinition,
    RelationDefinition,
    StandardProfile,
    TraceabilityRule,
)


def profile(profile_id: str, *, include_traceability: bool = False) -> StandardProfile:
    requirement = ElementTypeDefinition(
        id="requirement",
        kind=ElementKind.REQUIREMENT,
        attributes=[
            AttributeDefinition(id="text", type=AttributeType.STRING, required=True),
        ],
    )
    verification = ElementTypeDefinition(
        id="verification",
        kind=ElementKind.VERIFICATION,
    )
    relation = RelationDefinition(
        id="requirement_verified_by_verification",
        relation_type=RelationType.VERIFIED_BY,
        source_type_ids=["requirement"],
        target_type_ids=["verification"],
    )
    return StandardProfile(
        id=profile_id,
        version="1.0",
        name=profile_id,
        element_types=[requirement, verification],
        relations=[relation],
        traceability=(
            [
                TraceabilityRule(
                    id="requirement_requires_verification",
                    source_type_id="requirement",
                    relation_type=RelationType.VERIFIED_BY,
                    target_type_id="verification",
                )
            ]
            if include_traceability
            else []
        ),
    )


def test_composition_merges_non_conflicting_definitions() -> None:
    base = profile("base")
    extension = StandardProfile(
        id="extension",
        version="1.0",
        name="extension",
        element_types=[
            ElementTypeDefinition(id="safety_case", kind=ElementKind.SAFETY),
        ],
    )

    composed = StandardProfileEngine.compose(
        [base, extension], id="combined", version="1.0", name="Combined"
    )

    assert {item.id for item in composed.element_types} == {
        "requirement",
        "verification",
        "safety_case",
    }
    assert composed.metadata["composed_from"] == ["base@1.0", "extension@1.0"]


def test_composition_rejects_conflicting_definition() -> None:
    first = profile("first")
    second = StandardProfile(
        id="second",
        version="1.0",
        name="second",
        element_types=[ElementTypeDefinition(id="requirement", kind=ElementKind.SAFETY)],
    )

    try:
        StandardProfileEngine.compose(
            [first, second], id="combined", version="1.0", name="Combined"
        )
    except ProfileCompositionError as exc:
        assert "element_types" in str(exc)
        assert "requirement" in str(exc)
    else:
        raise AssertionError("conflicting definitions must be rejected")


def test_validation_requires_traceability_relation_definition() -> None:
    invalid = StandardProfile(
        id="invalid",
        version="1.0",
        name="invalid",
        element_types=[
            ElementTypeDefinition(id="requirement", kind=ElementKind.REQUIREMENT),
            ElementTypeDefinition(id="verification", kind=ElementKind.VERIFICATION),
        ],
        traceability=[
            TraceabilityRule(
                id="missing_relation",
                source_type_id="requirement",
                relation_type=RelationType.VERIFIED_BY,
                target_type_id="verification",
            )
        ],
    )

    try:
        StandardProfileEngine.validate_profile(invalid)
    except ProfileCompositionError as exc:
        assert "missing_relation" in str(exc)
    else:
        raise AssertionError("invalid traceability rule must be rejected")
