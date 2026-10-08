from uuid import uuid4

import pytest

from engineering_gateway.application.gateway_service import Actor
from engineering_gateway.application.tool_invocation import (
    ToolInvocationDenied,
    ToolInvocationRequest,
    ToolInvocationService,
)
from engineering_gateway.domain.audit import ActorType
from engineering_gateway.domain.change_control import AuthorizationLevel
from engineering_gateway.domain.tool_registry import (
    ToolDescriptor,
    ToolPermission,
    ToolRegistry,
    ToolSideEffect,
    ToolTrustLevel,
)


class FakeAdapter:
    async def execute(
        self, tool: ToolDescriptor, operation: str, arguments: dict[str, object]
    ) -> dict[str, object]:
        return {"received": arguments}


def make_tool(
    trust: ToolTrustLevel = ToolTrustLevel.ENGINEERING_VERIFIED,
    side_effect: ToolSideEffect = ToolSideEffect.READ,
) -> ToolDescriptor:
    return ToolDescriptor(
        tool_id="cad.export",
        name="CAD export",
        description="Export model",
        trust_level=trust,
        project_scoped=False,
        permissions=(
            ToolPermission(
                operation="export",
                authorization_level="L0_READ",
                side_effect=side_effect,
            ),
        ),
    )


@pytest.mark.asyncio
async def test_invocation_rechecks_policy_and_executes_registered_adapter() -> None:
    registry = ToolRegistry()
    registry.register(make_tool())
    service = ToolInvocationService(registry, {"cad.export": FakeAdapter()})
    actor = Actor("agent-1", ActorType.AI, AuthorizationLevel.L0_READ)

    result = await service.invoke(
        ToolInvocationRequest(
            tool_id="cad.export",
            operation="export",
            actor_id=actor.actor_id,
            authorization_level=actor.authorization_level,
            arguments={"format": "step"},
        ),
        actor,
        minimum_trust=ToolTrustLevel.ENGINEERING_VERIFIED,
    )

    assert result.ok is True
    assert result.output == {"received": {"format": "step"}}


@pytest.mark.asyncio
async def test_untrusted_tool_is_denied_at_invocation() -> None:
    registry = ToolRegistry()
    registry.register(make_tool(ToolTrustLevel.UNTRUSTED))
    service = ToolInvocationService(registry, {"cad.export": FakeAdapter()})
    actor = Actor("agent-1", ActorType.AI, AuthorizationLevel.L0_READ)

    with pytest.raises(ToolInvocationDenied, match="trust level"):
        await service.invoke(
            ToolInvocationRequest(
                tool_id="cad.export",
                operation="export",
                actor_id=actor.actor_id,
                authorization_level=actor.authorization_level,
            ),
            actor,
            minimum_trust=ToolTrustLevel.ENGINEERING_VERIFIED,
        )


@pytest.mark.asyncio
async def test_write_requires_declared_authorization() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolDescriptor(
            tool_id="cad.modify",
            name="CAD modify",
            description="Modify model",
            trust_level=ToolTrustLevel.ENGINEERING_VERIFIED,
            project_scoped=False,
            permissions=(
                ToolPermission(
                    operation="modify",
                    authorization_level="L2_MODIFY_WORKSPACE",
                    side_effect=ToolSideEffect.WRITE,
                ),
            ),
        )
    )
    service = ToolInvocationService(registry, {"cad.modify": FakeAdapter()})
    actor = Actor("agent-1", ActorType.AI, AuthorizationLevel.L1_PROPOSE)

    with pytest.raises(ToolInvocationDenied, match="authorization"):
        await service.invoke(
            ToolInvocationRequest(
                tool_id="cad.modify",
                operation="modify",
                actor_id=actor.actor_id,
                authorization_level=actor.authorization_level,
            ),
            actor,
            minimum_trust=ToolTrustLevel.ENGINEERING_VERIFIED,
        )


@pytest.mark.asyncio
async def test_physical_operation_is_fail_closed() -> None:
    registry = ToolRegistry()
    registry.register(make_tool(side_effect=ToolSideEffect.PHYSICAL))
    service = ToolInvocationService(registry, {"cad.export": FakeAdapter()})
    actor = Actor("agent-1", ActorType.AI, AuthorizationLevel.L2_MODIFY_WORKSPACE)

    with pytest.raises(ToolInvocationDenied, match="physical"):
        await service.invoke(
            ToolInvocationRequest(
                tool_id="cad.export",
                operation="export",
                actor_id=actor.actor_id,
                authorization_level=actor.authorization_level,
            ),
            actor,
            minimum_trust=ToolTrustLevel.ENGINEERING_VERIFIED,
        )


@pytest.mark.asyncio
async def test_ai_actor_cannot_execute_l3_tool_operation() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolDescriptor(
            tool_id="review.approve",
            name="Review approval",
            description="Restricted approval operation",
            trust_level=ToolTrustLevel.ENGINEERING_VERIFIED,
            project_scoped=False,
            permissions=(
                ToolPermission(
                    operation="approve",
                    authorization_level="L3_APPROVE",
                ),
            ),
        )
    )
    service = ToolInvocationService(registry, {"review.approve": FakeAdapter()})
    actor = Actor("agent-1", ActorType.AI, AuthorizationLevel.L3_APPROVE)

    with pytest.raises(ToolInvocationDenied, match="AI actors cannot execute L3"):
        await service.invoke(
            ToolInvocationRequest(
                tool_id="review.approve",
                operation="approve",
                actor_id=actor.actor_id,
                authorization_level=actor.authorization_level,
            ),
            actor,
        )


@pytest.mark.asyncio
async def test_invocation_rejects_actor_identity_mismatch() -> None:
    registry = ToolRegistry()
    registry.register(make_tool())
    service = ToolInvocationService(registry, {"cad.export": FakeAdapter()})
    actor = Actor("agent-1", ActorType.AI, AuthorizationLevel.L0_READ)

    with pytest.raises(ToolInvocationDenied, match="does not match current Actor"):
        await service.invoke(
            ToolInvocationRequest(
                tool_id="cad.export",
                operation="export",
                actor_id="spoofed",
                authorization_level=actor.authorization_level,
            ),
            actor,
            minimum_trust=ToolTrustLevel.ENGINEERING_VERIFIED,
        )
