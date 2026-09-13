"""Tests for application-level Standard Profile governance."""

from uuid import uuid4

import pytest

from engineering_gateway.application.gateway_service import Actor, GatewayApplicationService, GatewayServiceError
from engineering_gateway.domain.audit import ActorType, InMemoryAuditSink
from engineering_gateway.domain.models import ElementKind, EngineeringElement, RelationType
from engineering_gateway.domain.profiles import ElementTypeDefinition, RelationDefinition, StandardProfile
from engineering_gateway.domain.change_control import AuthorizationLevel
from engineering_gateway.infrastructure.profile_registry import InMemoryStandardProfileRegistry


def profile() -> StandardProfile:
    return StandardProfile(
        id="verification",
        version="1.0",
        name="Verification",
        element_types=[ElementTypeDefinition(id="requirement", kind=ElementKind.REQUIREMENT)],
        relations=[
            RelationDefinition(
                id="depends_on_requirement",
                relation_type=RelationType.DEPENDS_ON,
                source_type_ids=["requirement"],
                target_type_ids=["requirement"],
            )
        ],
    )


@pytest.mark.asyncio
async def test_gateway_rejects_registered_but_inactive_profile() -> None:
    registry = InMemoryStandardProfileRegistry()
    audit = InMemoryAuditSink()
    gateway = GatewayApplicationService(object(), registry, audit)
    registered = profile()
    await registry.register(registered)
    actor = Actor("reader", ActorType.HUMAN, AuthorizationLevel.L0_READ)

    with pytest.raises(GatewayServiceError, match="is not active"):
        await gateway.validate(actor, [], [], registered.id, registered.version)

    assert (await audit.list())[-1].result.value == "failure"


@pytest.mark.asyncio
async def test_gateway_validation_exposes_deterministic_graph_hash() -> None:
    registry = InMemoryStandardProfileRegistry()
    audit = InMemoryAuditSink()
    gateway = GatewayApplicationService(object(), registry, audit)
    registered = profile()
    await registry.register(registered)
    await registry.activate(registered.id, registered.version)
    actor = Actor("reader", ActorType.HUMAN, AuthorizationLevel.L0_READ)
    element = EngineeringElement(
        id=uuid4(),
        kind=ElementKind.REQUIREMENT,
        type_id="requirement",
        name="REQ-1",
        external_system="strictdoc",
        external_id="REQ-1",
    )

    first = await gateway.validate(actor, [element], [], registered.id, registered.version)
    second = await gateway.validate(actor, [element], [], registered.id, registered.version)

    assert first.graph_hash
    assert len(first.graph_hash) == 64
    assert first.graph_hash == second.graph_hash
    assert first.valid
