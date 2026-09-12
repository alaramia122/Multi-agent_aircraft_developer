from engineering_gateway.domain.models import ElementKind, EngineeringElement


def test_canonical_element_is_vendor_neutral() -> None:
    element = EngineeringElement(
        kind=ElementKind.ARCHITECTURE,
        type_id="system",
        name="Aircraft System",
        external_system="capella",
        external_id="capella:system:001",
    )

    assert not hasattr(element, "capella_model")
    assert not hasattr(element, "strictdoc_node")
