import pytest

from engineering_gateway.domain.models import ElementKind
from engineering_gateway.domain.profiles import ElementTypeDefinition, StandardProfile
from engineering_gateway.infrastructure.profile_registry import InMemoryStandardProfileRegistry


def make_profile(profile_id: str) -> StandardProfile:
    return StandardProfile(
        id=profile_id,
        version="1.0",
        name=profile_id,
        element_types=[ElementTypeDefinition(id="item", kind=ElementKind.GOVERNANCE)],
    )


@pytest.mark.asyncio
async def test_registry_round_trip_and_deterministic_listing() -> None:
    registry = InMemoryStandardProfileRegistry()
    first = make_profile("z-profile")
    second = make_profile("a-profile")

    await registry.register(first)
    await registry.register(second)

    assert await registry.get("z-profile", "1.0") == first
    assert [item.id for item in await registry.list()] == ["a-profile", "z-profile"]


@pytest.mark.asyncio
async def test_registry_rejects_different_duplicate_version() -> None:
    registry = InMemoryStandardProfileRegistry()
    await registry.register(make_profile("profile"))
    conflicting = make_profile("profile").model_copy(update={"name": "changed"})

    with pytest.raises(ValueError, match="already exists"):
        await registry.register(conflicting)
