from uuid import uuid4

from engineering_gateway.domain.models import (
    ElementKind,
    EngineeringElement,
    EngineeringRelation,
    RelationType,
)
from engineering_gateway.domain.profiles import (
    ElementTypeDefinition,
    RelationDefinition,
    StandardProfile,
    TraceabilityRule,
)
from engineering_gateway.domain.traceability import TraceabilityGapType, TraceabilityGraph


def element(type_id: str, kind: ElementKind) -> EngineeringElement:
    return EngineeringElement(
        kind=kind,
        type_id=type_id,
        name=type_id,
        external_system="test",
        external_id=str(uuid4()),
    )


def profile(*, required: bool = True) -> StandardProfile:
    return StandardProfile(
        id="traceability-gaps",
        version="1",
        name="Traceability gaps",
        element_types=[
            ElementTypeDefinition(id="requirement", kind=ElementKind.REQUIREMENT),
            ElementTypeDefinition(id="architecture", kind=ElementKind.ARCHITECTURE),
            ElementTypeDefinition(id="verification", kind=ElementKind.VERIFICATION),
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
                id="requirement-architecture",
                source_type_id="requirement",
                relation_type=RelationType.SATISFIES,
                target_type_id="architecture",
                required=required,
            )
        ],
    )


def test_missing_required_gap_type() -> None:
    requirement = element("requirement", ElementKind.REQUIREMENT)
    gaps = TraceabilityGraph([requirement], []).traceability_violations(profile())
    assert [gap.gap_type for gap in gaps] == [TraceabilityGapType.MISSING_REQUIRED]


def test_forbidden_present_gap_type() -> None:
    requirement = element("requirement", ElementKind.REQUIREMENT)
    architecture = element("architecture", ElementKind.ARCHITECTURE)
    relation = EngineeringRelation(
        source_id=requirement.id,
        relation_type=RelationType.SATISFIES,
        target_id=architecture.id,
    )
    gaps = TraceabilityGraph([requirement, architecture], [relation]).traceability_violations(
        profile(required=False)
    )
    assert [gap.gap_type for gap in gaps] == [TraceabilityGapType.FORBIDDEN_PRESENT]


def test_wrong_relation_type_gap_type() -> None:
    requirement = element("requirement", ElementKind.REQUIREMENT)
    architecture = element("architecture", ElementKind.ARCHITECTURE)
    relation = EngineeringRelation(
        source_id=requirement.id,
        relation_type=RelationType.DERIVES_FROM,
        target_id=architecture.id,
    )
    gaps = TraceabilityGraph([requirement, architecture], [relation]).traceability_violations(profile())
    assert [gap.gap_type for gap in gaps] == [TraceabilityGapType.WRONG_RELATION_TYPE]


def test_wrong_target_type_gap_type() -> None:
    requirement = element("requirement", ElementKind.REQUIREMENT)
    verification = element("verification", ElementKind.VERIFICATION)
    relation = EngineeringRelation(
        source_id=requirement.id,
        relation_type=RelationType.SATISFIES,
        target_id=verification.id,
    )
    gaps = TraceabilityGraph([requirement, verification], [relation]).traceability_violations(profile())
    assert [gap.gap_type for gap in gaps] == [TraceabilityGapType.WRONG_TARGET_TYPE]


def test_dangling_source_gap_type() -> None:
    missing_source = uuid4()
    architecture = element("architecture", ElementKind.ARCHITECTURE)
    relation = EngineeringRelation(
        source_id=missing_source,
        relation_type=RelationType.SATISFIES,
        target_id=architecture.id,
    )
    gaps = TraceabilityGraph([architecture], [relation]).traceability_violations(profile())
    assert any(gap.gap_type is TraceabilityGapType.DANGLING_SOURCE for gap in gaps)


def test_dangling_target_gap_type() -> None:
    requirement = element("requirement", ElementKind.REQUIREMENT)
    relation = EngineeringRelation(
        source_id=requirement.id,
        relation_type=RelationType.SATISFIES,
        target_id=uuid4(),
    )
    gaps = TraceabilityGraph([requirement], [relation]).traceability_violations(profile())
    assert any(gap.gap_type is TraceabilityGapType.DANGLING_TARGET for gap in gaps)
