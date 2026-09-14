import pytest

from engineering_gateway.application.profile_engine import (
    ProfileCompositionError,
    StandardProfileEngine,
)
from engineering_gateway.domain.models import ElementKind, RelationType
from engineering_gateway.domain.profiles import (
    ElementTypeDefinition,
    RelationDefinition,
    StandardProfile,
    TraceabilityRule,
    VerificationRule,
)
from engineering_gateway.infrastructure.profile_registry import InMemoryStandardProfileRegistry


def valid_profile(profile_id: str = "verification") -> StandardProfile:
    return StandardProfile(
        id=profile_id,
        version="1.0",
        name=profile_id,
        element_types=[
            ElementTypeDefinition(id="requirement", kind=ElementKind.REQUIREMENT),
            ElementTypeDefinition(id="verification", kind=ElementKind.VERIFICATION),
        ],
        relations=[
            RelationDefinition(
                id="verified_by",
                relation_type=RelationType.VERIFIED_BY,
                source_type_ids=["requirement"],
                target_type_ids=["verification"],
            )
        ],
        traceability=[
            TraceabilityRule(
                id="requirement_verification",
                source_type_id="requirement",
                relation_type=RelationType.VERIFIED_BY,
                target_type_id="verification",
            )
        ],
        verification=[
            VerificationRule(
                id="verification_exists",
                element_type_id="requirement",
                required_relation_type=RelationType.VERIFIED_BY,
                verification_type_id="verification",
            )
        ],
    )


@pytest.mark.asyncio
async def test_registry_requires_valid_profile_before_activation() -> None:
    registry = InMemoryStandardProfileRegistry()
    profile = valid_profile()
    await registry.register(profile)
    assert not await registry.is_active(profile.id, profile.version)
    activated = await registry.activate(profile.id, profile.version)
    assert activated == profile
    assert await registry.is_active(profile.id, profile.version)
    assert await registry.get_active() == [profile]


@pytest.mark.asyncio
async def test_registry_can_deactivate_profile() -> None:
    registry = InMemoryStandardProfileRegistry()
    profile = valid_profile()
    await registry.register(profile)
    await registry.activate(profile.id, profile.version)
    await registry.deactivate(profile.id, profile.version)
    assert not await registry.is_active(profile.id, profile.version)
    assert await registry.get_active() == []


def test_verification_rule_requires_matching_relation_definition() -> None:
    profile = valid_profile()
    invalid = profile.model_copy(update={"relations": []})
    with pytest.raises(ProfileCompositionError, match="matching relation definition"):
        StandardProfileEngine.validate_profile(invalid)
