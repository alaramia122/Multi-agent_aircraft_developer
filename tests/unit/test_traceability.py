from uuid import uuid4

import pytest

from engineering_gateway.domain.models import ElementKind, EngineeringElement, EngineeringRelation, RelationType
from engineering_gateway.domain.profiles import (
    ElementTypeDefinition,
    RelationDefinition,
    StandardProfile,
    TraceabilityRule,
)
from engineering_gateway.domain.traceability import TraceabilityGapType, TraceabilityGraph


def element(type_id: str, kind: ElementKind = ElementKind.REQUIREMENT) -> EngineeringElement:
    return EngineeringElement(
        kind=kind,
        type_id=type_id,
        name=type_id,
        external_system="test",
        external_id=str(uuid4()),
    )


def profile() -> StandardProfile:
    return StandardProfile(
        id="test-profile",
        version="1",
        name="Test profile",
        element_types=[
            ElementTypeDefinition(id="system_req", kind=ElementKind.REQUIREMENT),
            ElementTypeDefinition(id="system_arch", kind=ElementKind.ARCHITECTURE),
            ElementTypeDefinition(id="software_req", kind=ElementKind.REQUIREMENT),
        ],
        relations=[
            RelationDefinition(
                id="satisfies",
                relation_type=RelationType.SATISFIES,
                source_type_ids=["system_req"],
                target_type_ids=["system_arch"],
            )
        ],
        traceability=[
            TraceabilityRule(
                id="req-to-arch",
                source_type_id="system_req",
                relation_type=RelationType.SATISFIES,
                target_type_id="system_arch",
            )
        ],
    )


def relation(source: EngineeringElement, target: EngineeringElement, relation_type: RelationType) -> EngineeringRelation:
    return EngineeringRelation(source_id=source.id, relation_type=relation_type, target_id=target.id)


def test_required_traceability_gap_is_detected() -> None:
    source = element("system_req")
    gaps = TraceabilityGraph([source], []).missing_required(profile())

    assert len(gaps) == 1
    assert gaps[0].rule_id == "req-to-arch"
    assert gaps[0].source_id == source.id
    assert gaps[0].gap_type is TraceabilityGapType.MISSING_REQUIRED


def test_existing_traceability_is_not_reported() -> None:
    source = element("system_req")
    target = element("system_arch", ElementKind.ARCHITECTURE)
    graph = TraceabilityGraph([source, target], [relation(source, target, RelationType.SATISFIES)])

    assert graph.missing_required(profile()) == []


def test_outgoing_and_incoming_queries_are_directional() -> None:
    source = element("system_req")
    target = element("system_arch", ElementKind.ARCHITECTURE)
    edge = relation(source, target, RelationType.SATISFIES)
    graph = TraceabilityGraph([source, target], [edge])

    assert graph.outgoing(source.id) == [edge]
    assert graph.incoming(target.id) == [edge]
    assert graph.outgoing(target.id) == []


def test_reachable_and_ancestors_follow_directed_graph() -> None:
    source = element("system_req")
    middle = element("system_arch", ElementKind.ARCHITECTURE)
    target = element("software_req")
    graph = TraceabilityGraph(
        [source, middle, target],
        [relation(source, middle, RelationType.SATISFIES), relation(middle, target, RelationType.DERIVES_FROM)],
    )

    assert graph.reachable(source.id) == {middle.id, target.id}
    assert graph.reachable(source.id, RelationType.SATISFIES) == {middle.id}
    assert graph.ancestors(target.id) == {source.id, middle.id}


@pytest.mark.parametrize(
    ("relation_type", "expected"),
    [
        (RelationType.DERIVES_FROM, TraceabilityGapType.WRONG_RELATION_TYPE),
        (RelationType.VERIFIED_BY, TraceabilityGapType.WRONG_RELATION_TYPE),
    ],
)
def test_wrong_relation_type_is_diagnosed(relation_type: RelationType, expected: TraceabilityGapType) -> None:
    source = element("system_req")
    target = element("system_arch", ElementKind.ARCHITECTURE)
    gaps = TraceabilityGraph([source, target], [relation(source, target, relation_type)]).traceability_violations(profile())

    assert any(gap.gap_type is expected for gap in gaps)


def test_wrong_target_type_is_diagnosed() -> None:
    source = element("system_req")
    wrong_target = element("software_req")
    gaps = TraceabilityGraph(
        [source, wrong_target], [relation(source, wrong_target, RelationType.SATISFIES)]
    ).traceability_violations(profile())

    assert any(gap.gap_type is TraceabilityGapType.WRONG_TARGET_TYPE for gap in gaps)


def test_dangling_target_is_diagnosed() -> None:
    source = element("system_req")
    missing_target = uuid4()
    edge = EngineeringRelation(
        source_id=source.id,
        relation_type=RelationType.SATISFIES,
        target_id=missing_target,
    )
    gaps = TraceabilityGraph([source], [edge]).traceability_violations(profile())

    assert any(gap.gap_type is TraceabilityGapType.DANGLING_TARGET for gap in gaps)


def test_dangling_source_is_diagnosed() -> None:
    source_id = uuid4()
    target = element("system_arch", ElementKind.ARCHITECTURE)
    edge = EngineeringRelation(
        source_id=source_id,
        relation_type=RelationType.SATISFIES,
        target_id=target.id,
    )
    gaps = TraceabilityGraph([target], [edge]).traceability_violations(profile())

    assert any(gap.gap_type is TraceabilityGapType.DANGLING_SOURCE for gap in gaps)


def test_forbidden_traceability_is_reported() -> None:
    source = element("system_req")
    target = element("system_arch", ElementKind.ARCHITECTURE)
    edge = relation(source, target, RelationType.SATISFIES)
    forbidden_profile = profile().model_copy(
        update={
            "traceability": [
                TraceabilityRule(
                    id="req-must-not-satisfy-arch",
                    source_type_id="system_req",
                    relation_type=RelationType.SATISFIES,
                    target_type_id="system_arch",
                    required=False,
                )
            ]
        }
    )

    gaps = TraceabilityGraph([source, target], [edge]).traceability_violations(forbidden_profile)

    assert len(gaps) == 1
    assert gaps[0].forbidden is True
    assert gaps[0].gap_type is TraceabilityGapType.FORBIDDEN_PRESENT
