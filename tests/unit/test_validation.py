from uuid import uuid4

from engineering_gateway.application.validation import DeterministicValidationEngine
from engineering_gateway.domain.models import ElementKind, EngineeringElement, EngineeringRelation, RelationType
from engineering_gateway.domain.profiles import ElementTypeDefinition, RelationDefinition, StandardProfile, TraceabilityRule


def make_element(type_id: str, kind: ElementKind) -> EngineeringElement:
    return EngineeringElement(
        kind=kind,
        type_id=type_id,
        name=type_id,
        external_system="test",
        external_id=str(uuid4()),
    )


def make_profile() -> StandardProfile:
    return StandardProfile(
        id="validation-profile",
        version="1",
        name="Validation profile",
        element_types=[
            ElementTypeDefinition(id="requirement", kind=ElementKind.REQUIREMENT),
            ElementTypeDefinition(id="architecture", kind=ElementKind.ARCHITECTURE),
        ],
        relations=[
            RelationDefinition(
                id="satisfies",
                relation_type=RelationType.SATISFIES,
                source_type_ids=["requirement"],
                target_type_ids=["architecture"],
            )
        ],
        traceability=[
            TraceabilityRule(
                id="required-satisfaction",
                source_type_id="requirement",
                relation_type=RelationType.SATISFIES,
                target_type_id="architecture",
            )
        ],
    )


def test_unknown_element_type_is_reported() -> None:
    element = make_element("unknown", ElementKind.REQUIREMENT)

    issues = DeterministicValidationEngine().validate([element], [], make_profile())

    assert [issue.code for issue in issues] == ["UNKNOWN_ELEMENT_TYPE"]


def test_dangling_relation_is_reported() -> None:
    source = make_element("requirement", ElementKind.REQUIREMENT)
    relation = EngineeringRelation(
        source_id=source.id,
        relation_type=RelationType.SATISFIES,
        target_id=uuid4(),
    )

    issues = DeterministicValidationEngine().validate([source], [relation], make_profile())

    assert any(issue.code == "DANGLING_RELATION" for issue in issues)


def test_forbidden_relation_is_reported() -> None:
    source = make_element("requirement", ElementKind.REQUIREMENT)
    target = make_element("architecture", ElementKind.ARCHITECTURE)
    relation = EngineeringRelation(
        source_id=source.id,
        relation_type=RelationType.DERIVES_FROM,
        target_id=target.id,
    )

    issues = DeterministicValidationEngine().validate([source, target], [relation], make_profile())

    assert any(issue.code == "FORBIDDEN_RELATION" for issue in issues)


def test_missing_required_traceability_is_reported() -> None:
    source = make_element("requirement", ElementKind.REQUIREMENT)

    issues = DeterministicValidationEngine().validate([source], [], make_profile())

    assert any(issue.code == "MISSING_TRACEABILITY" for issue in issues)


def test_valid_graph_has_no_issues() -> None:
    source = make_element("requirement", ElementKind.REQUIREMENT)
    target = make_element("architecture", ElementKind.ARCHITECTURE)
    relation = EngineeringRelation(
        source_id=source.id,
        relation_type=RelationType.SATISFIES,
        target_id=target.id,
    )

    issues = DeterministicValidationEngine().validate([source, target], [relation], make_profile())

    assert issues == []
