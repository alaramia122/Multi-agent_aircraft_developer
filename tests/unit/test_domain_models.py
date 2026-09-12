from engineering_gateway.domain.models import ElementKind, EngineeringElement


def test_engineering_element_keeps_external_identity() -> None:
    element = EngineeringElement(
        kind=ElementKind.REQUIREMENT,
        type_id="system_requirement",
        name="SR-001",
        external_system="strictdoc",
        external_id="REQ-001",
    )

    assert element.external_system == "strictdoc"
    assert element.external_id == "REQ-001"
