from uuid import uuid4

import pytest

from engineering_gateway.domain.models import ElementKind, EngineeringElement, EngineeringRelation, RelationType
from engineering_gateway.domain.profiles import (
    ElementTypeDefinition,
    RelationDefinition,
    StandardProfile,
    TraceabilityRule,
)
from engineering_gateway.domain.traceability import TraceabilityGraph


def element(type_id: str) -> EngineeringElement:
    return EngineeringElement(
        kind=ElementKind.REQUIREMENT,
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


def test_required_traceability_gap_is_detected() -> None:
    source = element("system_req")
    graph = TraceabilityGraph([source], [])

    gaps = graph.missing_required(profile())

    assert len(gaps) == 1
    assert gaps[0].rule_id == "req-to-arch"
    assert gaps[0].source_id == source.id


def test_existing_traceability_is_not_reported() -> None:
    source = element("system_req")
    target = element("system_arch")
    relation = EngineeringRelation(
        source_id=source.id,
        relation_type=RelationType.SATISFIES,
        target_id=target.id,
    )
    graph = TraceabilityGraph([source, target], [relation])

    assert graph.missing_required(profile()) == []


def test_outgoing_and_incoming_queries_are_directional() -> None:
    source = element("system_req")
    target = element("system_arch")
    relation = EngineeringRelation(
        source_id=source.id,
        relation_type=RelationType.SATISFIES,
        target_id=target.id,
    )
    graph = TraceabilityGraph([source, target], [relation])

    assert graph.outgoing(source.id) == [relation]
    assert graph.incoming(target.id) == [relation]
    assert graph.outgoing(target.id) == []


@pytest.mark.parametrize("relation_type", [RelationType.DERIVES_FROM, RelationType.VERIFIED_BY])
def test_wrong_relation_type_does_not_satisfy_rule(relation_type: RelationType) -> None:
    source = element("system_req")
    target = element("system_arch")
    relation = EngineeringRelation(
        source_id=source.id,
        relation_type=relation_type,
        target_id=target.id,
    )
    graph = TraceabilityGraph([source, target], [relation])

    assert len(graph.missing_required(profile())) == 1


def test_forbidden_traceability_is_reported() -> None:
    source = element("system_req")
    target = element("system_arch")
    relation = EngineeringRelation(
        source_id=source.id,
        relation_type=RelationType.SATISFIES,
        target_id=target.id,
    )
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

    gaps = TraceabilityGraph([source, target], [relation]).traceability_violations(
        forbidden_profile
    )

    assert len(gaps) == 1
    assert gaps[0].forbidden is True
