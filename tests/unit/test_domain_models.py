from uuid import uuid4

import pytest
from pydantic import ValidationError

from engineering_gateway.domain.models import (
    ElementKind,
    EngineeringElement,
    EngineeringGraph,
    EngineeringRelation,
    RelationType,
)


def test_engineering_element_preserves_external_identity() -> None:
    element = EngineeringElement(
        kind=ElementKind.REQUIREMENT,
        type_id="system-requirement",
        name="Landing gear shall deploy",
        external_system="strictdoc",
        external_id="REQ-001",
    )

    assert element.external_system == "strictdoc"
    assert element.external_id == "REQ-001"


def test_relation_is_typed_and_directed() -> None:
    source = uuid4()
    target = uuid4()
    relation = EngineeringRelation(
        source_id=source,
        relation_type=RelationType.VERIFIED_BY,
        target_id=target,
    )

    assert relation.source_id == source
    assert relation.target_id == target
    assert relation.relation_type is RelationType.VERIFIED_BY


def test_graph_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        EngineeringGraph(bad_field="must not become a hidden model")
