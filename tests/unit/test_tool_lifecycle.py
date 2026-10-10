import pytest
from pydantic import ValidationError

from engineering_gateway.application.gateway_service import Actor
from engineering_gateway.application.tool_lifecycle import (
    ToolLifecycleDenied,
    ToolLifecycleService,
    ToolReviewDecision,
)
from engineering_gateway.domain.audit import ActorType, AuditResult, InMemoryAuditSink
from engineering_gateway.domain.change_control import AuthorizationLevel
from engineering_gateway.domain.tool_registry import (
    ToolDescriptor,
    ToolLifecycleState,
    ToolPermission,
    ToolRegistry,
    ToolTrustLevel,
)


def pending_tool() -> ToolDescriptor:
    return ToolDescriptor(
        tool_id="custom.analysis",
        name="Custom analysis",
        description="A user-provided tool awaiting review",
        trust_level=ToolTrustLevel.UNTRUSTED,
        enabled=False,
        lifecycle_state=ToolLifecycleState.PENDING_REVIEW,
        project_scoped=True,
        permissions=(
            ToolPermission(operation="analyze", authorization_level="L0_READ"),
        ),
    )


def reviewer(level: AuthorizationLevel = AuthorizationLevel.L3_APPROVE) -> Actor:
    return Actor("human-reviewer", ActorType.HUMAN, level)


@pytest.mark.asyncio
async def test_l3_human_review_activates_custom_tool_only_at_sandbox() -> None:
    registry = ToolRegistry()
    registry.register(pending_tool())
    audit = InMemoryAuditSink()
    service = ToolLifecycleService(registry, audit)

    result = await service.review(
        "custom.analysis",
        ToolReviewDecision(
            accepted=True,
            reason="Contract and isolated behavior reviewed",
            evidence_uri="https://engineering.example/reviews/custom-analysis",
        ),
        reviewer(),
    )

    assert result.lifecycle_state is ToolLifecycleState.ACTIVE
    assert result.trust_level is ToolTrustLevel.SANDBOX
    assert result.enabled is True
    events = await audit.list()
    assert len(events) == 1
    assert events[0].action == "tool_lifecycle"
    assert events[0].result is AuditResult.SUCCESS


@pytest.mark.asyncio
async def test_tool_review_rejection_keeps_tool_disabled_and_untrusted() -> None:
    registry = ToolRegistry()
    registry.register(pending_tool())
    service = ToolLifecycleService(registry, InMemoryAuditSink())

    result = await service.review(
        "custom.analysis",
        ToolReviewDecision(accepted=False, reason="Missing isolation evidence"),
        reviewer(),
    )

    assert result.lifecycle_state is ToolLifecycleState.REJECTED
    assert result.trust_level is ToolTrustLevel.UNTRUSTED
    assert result.enabled is False


@pytest.mark.asyncio
async def test_tool_review_requires_human_l3() -> None:
    registry = ToolRegistry()
    registry.register(pending_tool())
    service = ToolLifecycleService(registry, InMemoryAuditSink())

    with pytest.raises(ToolLifecycleDenied, match="only human"):
        await service.review(
            "custom.analysis",
            ToolReviewDecision(
                accepted=True,
                reason="Not enough authority",
                evidence_uri="https://engineering.example/evidence",
            ),
            Actor("agent", ActorType.AI, AuthorizationLevel.L3_APPROVE),
        )

    with pytest.raises(ToolLifecycleDenied, match="human L3"):
        await service.review(
            "custom.analysis",
            ToolReviewDecision(accepted=False, reason="Not L3"),
            reviewer(AuthorizationLevel.L2_MODIFY_WORKSPACE),
        )


def test_accepted_tool_review_requires_https_evidence() -> None:
    with pytest.raises(ValidationError, match="HTTPS evidence URI"):
        ToolReviewDecision(
            accepted=True,
            reason="Review completed",
            evidence_uri="file:///tmp/evidence",
        )


@pytest.mark.asyncio
async def test_tool_review_is_single_transition_and_replay_is_denied() -> None:
    registry = ToolRegistry()
    registry.register(pending_tool())
    service = ToolLifecycleService(registry, InMemoryAuditSink())
    decision = ToolReviewDecision(accepted=False, reason="Rejected for testing")

    await service.review("custom.analysis", decision, reviewer())

    with pytest.raises(ToolLifecycleDenied, match="not pending review"):
        await service.review("custom.analysis", decision, reviewer())


@pytest.mark.asyncio
async def test_human_l2_can_revoke_active_tool_with_audit() -> None:
    registry = ToolRegistry()
    active = pending_tool().model_copy(update={
        "lifecycle_state": ToolLifecycleState.ACTIVE,
        "trust_level": ToolTrustLevel.SANDBOX,
        "enabled": True,
    })
    registry.register(active)
    audit = InMemoryAuditSink()
    service = ToolLifecycleService(registry, audit)

    result = await service.revoke("custom.analysis", reviewer(AuthorizationLevel.L2_MODIFY_WORKSPACE), "Security concern")

    assert result.lifecycle_state is ToolLifecycleState.REVOKED
    assert result.trust_level is ToolTrustLevel.UNTRUSTED
    assert result.enabled is False
    assert (await audit.list())[-1].result is AuditResult.SUCCESS



@pytest.mark.asyncio
async def test_pending_review_queue_is_human_only_and_deterministic() -> None:
    registry = ToolRegistry()
    registry.register(pending_tool())
    active = pending_tool().model_copy(update={
        "tool_id": "custom.active",
        "lifecycle_state": ToolLifecycleState.ACTIVE,
        "trust_level": ToolTrustLevel.SANDBOX,
        "enabled": True,
    })
    registry.register(active)
    service = ToolLifecycleService(registry, InMemoryAuditSink())

    pending = await service.list_pending(reviewer(AuthorizationLevel.L2_MODIFY_WORKSPACE))

    assert [tool.tool_id for tool in pending] == ["custom.analysis"]
    with pytest.raises(ToolLifecycleDenied, match="only human"):
        await service.list_pending(Actor("agent", ActorType.AI, AuthorizationLevel.L2_MODIFY_WORKSPACE))
