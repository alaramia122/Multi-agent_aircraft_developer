"""Tests for the governed Gateway application service."""

from uuid import uuid4

import pytest

from engineering_gateway.application.gateway_service import (
    Actor,
    GatewayApplicationService,
    GatewayServiceError,
)
from engineering_gateway.domain.audit import ActorType, InMemoryAuditSink
from engineering_gateway.domain.change_control import AuthorizationLevel
from engineering_gateway.domain.models import ElementKind, EngineeringElement
from engineering_gateway.infrastructure.profile_registry import InMemoryStandardProfileRegistry


@pytest.fixture
def actor_read() -> Actor:
    return Actor("human-reader", ActorType.HUMAN, AuthorizationLevel.L0_READ)


@pytest.fixture
def actor_ai() -> Actor:
    return Actor("agent", ActorType.AI, AuthorizationLevel.L3_APPROVE)


@pytest.fixture
def service(repository, actor_read: Actor):
    audit = InMemoryAuditSink()
    profiles = InMemoryStandardProfileRegistry()
    return GatewayApplicationService(repository, profiles, audit), audit


@pytest.mark.asyncio
async def test_read_is_audited(service, actor_read: Actor, repository) -> None:
    gateway, audit = service
    element = EngineeringElement(
        kind=ElementKind.REQUIREMENT,
        type_id="requirement",
        name="REQ-1",
        external_system="strictdoc",
        external_id="REQ-1",
    )
    await repository.save(element)

    result = await gateway.get_element(actor_read, element.id)

    assert result == element
    events = await audit.list()
    assert events[-1].action == "get_element"
    assert events[-1].result.value == "success"


@pytest.mark.asyncio
async def test_ai_cannot_approve(service, actor_ai: Actor) -> None:
    gateway, audit = service
    baseline_id = uuid4()

    with pytest.raises(GatewayServiceError, match="human L3 approver"):
        await gateway.approve(actor_ai, baseline_id)

    events = await audit.list()
    assert events[-1].result.value == "denied"


@pytest.mark.asyncio
async def test_l2_workspace_write_is_audited(service, repository) -> None:
    gateway, audit = service
    actor = Actor("engineer", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE)
    workspace_id = uuid4()
    element = EngineeringElement(
        kind=ElementKind.REQUIREMENT,
        type_id="requirement",
        name="REQ-2",
        external_system="strictdoc",
        external_id="REQ-2",
    )

    result = await gateway.save_workspace_element(actor, element, workspace_id)

    assert result == element
    events = await audit.list()
    assert events[-1].action == "save_workspace_element"
    assert events[-1].metadata["workspace_id"] == str(workspace_id)


@pytest.mark.asyncio
async def test_read_actor_cannot_write_workspace(service, actor_read: Actor) -> None:
    gateway, audit = service
    element = EngineeringElement(
        kind=ElementKind.REQUIREMENT,
        type_id="requirement",
        name="REQ-3",
        external_system="strictdoc",
        external_id="REQ-3",
    )

    with pytest.raises(GatewayServiceError, match="only L2"):
        await gateway.save_workspace_element(actor_read, element, uuid4())

    events = await audit.list()
    assert events[-1].result.value == "denied"


@pytest.mark.asyncio
async def test_unknown_profile_is_rejected_and_audited(service, actor_read: Actor) -> None:
    gateway, audit = service

    result = None
    with pytest.raises(GatewayServiceError, match="was not found"):
        result = await gateway.validate(actor_read, [], [], "missing", "1.0")

    assert result is None
    events = await audit.list()
    assert events[-1].action == "validate"
    assert events[-1].result.value == "failure"
