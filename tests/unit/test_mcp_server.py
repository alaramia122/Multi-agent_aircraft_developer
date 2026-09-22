"""Tests for the governed MCP Gateway surface."""

from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from engineering_gateway.api.mcp_server import create_mcp_server
from engineering_gateway.application.gateway_service import Actor, GatewayApplicationService
from engineering_gateway.application.governed_gateway_service import GovernedGatewayApplicationService
from engineering_gateway.application.validation import ValidationResult
from engineering_gateway.domain.audit import ActorType, InMemoryAuditSink
from engineering_gateway.domain.change_control import AuthorizationLevel
from engineering_gateway.domain.models import (
    ElementKind,
    EngineeringElement,
    EngineeringRelation,
    RelationType,
)
from engineering_gateway.infrastructure.profile_registry import InMemoryStandardProfileRegistry


class _Repository:
    def __init__(self) -> None:
        self.element = EngineeringElement(
            kind=ElementKind.REQUIREMENT,
            type_id="requirement",
            name="Requirement",
            external_system="strictdoc",
            external_id="REQ-1",
            source_uri="strictdoc://requirements#REQ-1",
        )
        self.relation = EngineeringRelation(
            source_id=self.element.id,
            relation_type=RelationType.DERIVES_FROM,
            target_id=uuid4(),
        )

    async def get(self, element_id: UUID) -> EngineeringElement | None:
        return self.element if element_id == self.element.id else None

    async def save(self, element: EngineeringElement) -> EngineeringElement:
        self.element = element
        return element

    async def add_relation(self, relation: EngineeringRelation) -> EngineeringRelation:
        self.relation = relation
        return relation

    async def get_relations(self, element_id: UUID) -> list[EngineeringRelation]:
        return [self.relation] if element_id == self.element.id else []


def _service(repository: _Repository) -> GatewayApplicationService:
    return GatewayApplicationService(
        repository,
        InMemoryStandardProfileRegistry(),
        InMemoryAuditSink(),
    )


def _factory(service: GatewayApplicationService):
    @asynccontextmanager
    async def context():
        yield service

    return context


def _actor(level: AuthorizationLevel = AuthorizationLevel.L0_READ) -> Actor:
    return Actor("mcp-ai", ActorType.AI, level)


class _MutableActorProvider:
    def __init__(self, actor: Actor) -> None:
        self.actor = actor
        self.calls = 0

    def get_actor(self) -> Actor:
        self.calls += 1
        return self.actor


class _EvidenceService(GatewayApplicationService):
    def __init__(self, repository: _Repository) -> None:
        super().__init__(
            repository,
            InMemoryStandardProfileRegistry(),
            InMemoryAuditSink(),
        )
        self.validation_evidence = None

    async def validate(self, actor, elements, relations, profile_id, profile_version, **kwargs):
        self.validation_evidence = kwargs
        return ValidationResult(profile_id, profile_version, "graph-hash", ())


class _EvidenceGovernedService(GovernedGatewayApplicationService):
    def __init__(self, repository: _Repository) -> None:
        super().__init__(
            repository,
            InMemoryStandardProfileRegistry(),
            InMemoryAuditSink(),
        )
        self.approval_evidence = None

    async def prepare_for_approval(self, actor, workspace_id, **kwargs):
        self.approval_evidence = kwargs
        return ValidationResult(kwargs["profile_id"], kwargs["profile_version"], "graph-hash", ())


@pytest.mark.asyncio
async def test_l0_mcp_server_exposes_all_tools_but_enforces_l2_at_invocation() -> None:
    repository = _Repository()
    server = create_mcp_server(_factory(_service(repository)), _actor())

    tools = await server.list_tools()
    names = {tool.name for tool in tools}

    assert {
        "get_engineering_element",
        "get_engineering_relations",
        "validate_engineering_graph",
        "create_workspace",
        "save_workspace_element",
        "add_workspace_relation",
        "prepare_workspace_for_approval",
        "reconcile_workspace",
    } == names

    with pytest.raises(ToolError, match="MCP workspace mutation requires L2 authorization"):
        await server.call_tool(
            "create_workspace",
            {"baseline_id": str(uuid4()), "change_request_id": str(uuid4())},
        )


@pytest.mark.asyncio
async def test_l1_mcp_server_cannot_mutate_workspace() -> None:
    repository = _Repository()
    server = create_mcp_server(
        _factory(_service(repository)), _actor(AuthorizationLevel.L1_PROPOSE)
    )

    with pytest.raises(ToolError, match="MCP workspace mutation requires L2 authorization"):
        await server.call_tool(
            "create_workspace",
            {"baseline_id": str(uuid4()), "change_request_id": str(uuid4())},
        )


@pytest.mark.asyncio
async def test_l2_mcp_server_exposes_workspace_mutation_tools_but_no_approval() -> None:
    repository = _Repository()
    server = create_mcp_server(
        _factory(_service(repository)), _actor(AuthorizationLevel.L2_MODIFY_WORKSPACE)
    )

    tools = await server.list_tools()
    names = {tool.name for tool in tools}

    assert {
        "create_workspace",
        "save_workspace_element",
        "add_workspace_relation",
    }.issubset(names)
    assert "approve_workspace" not in names
    assert "reject_workspace" not in names


@pytest.mark.asyncio
async def test_mcp_tool_returns_canonical_element() -> None:
    repository = _Repository()
    server = create_mcp_server(_factory(_service(repository)), _actor())

    result = await server.call_tool(
        "get_engineering_element", {"element_id": str(repository.element.id)}
    )

    assert result is not None


@pytest.mark.asyncio
async def test_mcp_tool_rejects_invalid_uuid_at_boundary() -> None:
    repository = _Repository()
    server = create_mcp_server(_factory(_service(repository)), _actor())

    with pytest.raises(ToolError, match="element_id must be a valid UUID"):
        await server.call_tool("get_engineering_element", {"element_id": "not-a-uuid"})


@pytest.mark.asyncio
async def test_mcp_validation_rejects_blank_profile_identity_at_boundary() -> None:
    repository = _Repository()
    server = create_mcp_server(_factory(_service(repository)), _actor())

    with pytest.raises(ToolError, match="profile_id must not be blank"):
        await server.call_tool(
            "validate_engineering_graph",
            {
                "elements": [],
                "relations": [],
                "profile_id": "   ",
                "profile_version": "1.0",
            },
        )


@pytest.mark.asyncio
async def test_mcp_validation_forwards_typed_profile_evidence() -> None:
    repository = _Repository()
    service = _EvidenceService(repository)
    server = create_mcp_server(_factory(service), _actor())
    element_id = repository.element.id

    await server.call_tool(
        "validate_engineering_graph",
        {
            "elements": [repository.element.model_dump(mode="json")],
            "relations": [],
            "profile_id": "profile",
            "profile_version": "2.0",
            "validation_attributes": [
                {"element_id": str(element_id), "attributes": {"dal": "A"}}
            ],
            "artifact_evidence": [
                {"element_id": str(element_id), "artifact_type": "review_record"}
            ],
            "lifecycle_states": [{"element_id": str(element_id), "state": "reviewed"}],
            "lifecycle_transitions": [
                {
                    "element_id": str(element_id),
                    "source_state": "draft",
                    "target_state": "reviewed",
                }
            ],
        },
    )

    assert service.validation_evidence == {
        "validation_attributes": {element_id: {"dal": "A"}},
        "artifact_evidence": {(element_id, "review_record")},
        "lifecycle_states": {element_id: "reviewed"},
        "lifecycle_transitions": {element_id: ("draft", "reviewed")},
    }


@pytest.mark.asyncio
async def test_mcp_approval_preparation_forwards_typed_profile_evidence() -> None:
    repository = _Repository()
    service = _EvidenceGovernedService(repository)
    server = create_mcp_server(
        _factory(service), _actor(AuthorizationLevel.L2_MODIFY_WORKSPACE)
    )
    workspace_id = uuid4()
    element_id = repository.element.id

    await server.call_tool(
        "prepare_workspace_for_approval",
        {
            "workspace_id": str(workspace_id),
            "profile_id": "profile",
            "profile_version": "2.0",
            "lifecycle_states": [{"element_id": str(element_id), "state": "reviewed"}],
        },
    )

    assert service.approval_evidence == {
        "profile_id": "profile",
        "profile_version": "2.0",
        "validation_attributes": {},
        "artifact_evidence": set(),
        "lifecycle_states": {element_id: "reviewed"},
        "lifecycle_transitions": {},
    }


@pytest.mark.asyncio
async def test_l2_mutating_tools_are_not_read_only() -> None:
    repository = _Repository()
    server = create_mcp_server(
        _factory(_service(repository)), _actor(AuthorizationLevel.L2_MODIFY_WORKSPACE)
    )

    tools = await server.list_tools()
    by_name = {tool.name: tool for tool in tools}

    for name in (
        "create_workspace",
        "save_workspace_element",
        "add_workspace_relation",
        "prepare_workspace_for_approval",
        "reconcile_workspace",
    ):
        assert by_name[name].annotations is not None
        assert not by_name[name].annotations.read_only_hint
        assert by_name[name].annotations.destructive_hint is False


@pytest.mark.asyncio
async def test_mcp_does_not_expose_l3_approval_even_for_l3_human_actor() -> None:
    repository = _Repository()
    server = create_mcp_server(
        _factory(_service(repository)),
        Actor("operator", ActorType.HUMAN, AuthorizationLevel.L3_APPROVE),
    )

    tools = await server.list_tools()
    names = {tool.name for tool in tools}

    assert "approve_workspace" not in names
    assert "reject_workspace" not in names
    assert "approve_baseline" not in names


@pytest.mark.asyncio
async def test_mcp_operation_acquires_a_fresh_service_context() -> None:
    repository = _Repository()
    service = _service(repository)
    opened = 0
    closed = 0

    @asynccontextmanager
    async def factory():
        nonlocal opened, closed
        opened += 1
        try:
            yield service
        finally:
            closed += 1

    server = create_mcp_server(factory, _actor())
    await server.call_tool("get_engineering_element", {"element_id": str(repository.element.id)})
    await server.call_tool("get_engineering_element", {"element_id": str(repository.element.id)})

    assert opened == 2
    assert closed == 2


@pytest.mark.asyncio
async def test_mcp_resolves_actor_for_each_operation() -> None:
    repository = _Repository()
    provider = _MutableActorProvider(_actor())
    server = create_mcp_server(_factory(_service(repository)), provider)

    await server.call_tool("get_engineering_element", {"element_id": str(repository.element.id)})
    provider.actor = _actor(AuthorizationLevel.L1_PROPOSE)
    await server.call_tool("get_engineering_element", {"element_id": str(repository.element.id)})

    assert provider.calls == 2


@pytest.mark.asyncio
async def test_mcp_runtime_authorization_follows_current_actor() -> None:
    repository = _Repository()
    provider = _MutableActorProvider(_actor(AuthorizationLevel.L0_READ))
    server = create_mcp_server(_factory(_service(repository)), provider)

    with pytest.raises(ToolError, match="MCP workspace mutation requires L2 authorization"):
        await server.call_tool(
            "create_workspace",
            {"baseline_id": str(uuid4()), "change_request_id": str(uuid4())},
        )

    provider.actor = _actor(AuthorizationLevel.L2_MODIFY_WORKSPACE)
    await server.list_tools()
    assert provider.calls == 1
