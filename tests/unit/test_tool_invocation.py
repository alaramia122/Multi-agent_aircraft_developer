from uuid import uuid4

import pytest

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
    async def execute(self, tool, operation, arguments):
        return {"received": arguments}


def make_tool(trust=ToolTrustLevel.ENGINEERING_VERIFIED, side_effect=ToolSideEffect.READ):
    return ToolDescriptor(
        tool_id="cad.export",
        name="CAD export",
        description="Export model",
        trust_level=trust,
        permissions=(
            ToolPermission(
                operation="export",
                authorization_level="L0_READ",
                side_effect=side_effect,
            ),
        ),
    )


@pytest.mark.asyncio
async def test_invocation_rechecks_policy_and_executes_registered_adapter():
    registry = ToolRegistry()
    registry.register(make_tool())
    service = ToolInvocationService(registry, {"cad.export": FakeAdapter()})
    project_id = uuid4()

    result = await service.invoke(
        ToolInvocationRequest(
            tool_id="cad.export",
            operation="export",
            actor_id="agent-1",
            authorization_level=AuthorizationLevel.L0_READ,
            project_id=project_id,
            arguments={"format": "step"},
        ),
        minimum_trust=ToolTrustLevel.ENGINEERING_VERIFIED,
        project_id=project_id,
    )

    assert result.ok is True
    assert result.output == {"received": {"format": "step"}}


@pytest.mark.asyncio
async def test_untrusted_tool_is_denied_at_invocation():
    registry = ToolRegistry()
    registry.register(make_tool(ToolTrustLevel.UNTRUSTED))
    service = ToolInvocationService(registry, {"cad.export": FakeAdapter()})

    with pytest.raises(ToolInvocationDenied, match="trust level"):
        await service.invoke(
            ToolInvocationRequest(
                tool_id="cad.export",
                operation="export",
                actor_id="agent-1",
                authorization_level=AuthorizationLevel.L0_READ,
                project_id=uuid4(),
            ),
            minimum_trust=ToolTrustLevel.ENGINEERING_VERIFIED,
        )


@pytest.mark.asyncio
async def test_write_requires_declared_authorization():
    registry = ToolRegistry()
    registry.register(
        ToolDescriptor(
            tool_id="cad.modify",
            name="CAD modify",
            description="Modify model",
            trust_level=ToolTrustLevel.ENGINEERING_VERIFIED,
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

    with pytest.raises(ToolInvocationDenied, match="authorization"):
        await service.invoke(
            ToolInvocationRequest(
                tool_id="cad.modify",
                operation="modify",
                actor_id="agent-1",
                authorization_level=AuthorizationLevel.L1_PROPOSE,
                project_id=uuid4(),
            ),
            minimum_trust=ToolTrustLevel.ENGINEERING_VERIFIED,
        )


@pytest.mark.asyncio
async def test_physical_operation_is_fail_closed():
    registry = ToolRegistry()
    registry.register(make_tool(side_effect=ToolSideEffect.PHYSICAL))
    service = ToolInvocationService(registry, {"cad.export": FakeAdapter()})

    with pytest.raises(ToolInvocationDenied, match="physical"):
        await service.invoke(
            ToolInvocationRequest(
                tool_id="cad.export",
                operation="export",
                actor_id="agent-1",
                authorization_level=AuthorizationLevel.L2_MODIFY_WORKSPACE,
                project_id=uuid4(),
            ),
            Actor("agent-1", ActorType.AI, AuthorizationLevel.L2_MODIFY_WORKSPACE),
            minimum_trust=ToolTrustLevel.ENGINEERING_VERIFIED,
        )
