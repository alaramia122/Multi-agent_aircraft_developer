"""Application boundary for authoritative OpenProject change requests."""

from uuid import UUID

from engineering_gateway.application.gateway_service import Actor, GatewayServiceError
from engineering_gateway.domain.adapters import OpenProjectAdapter
from engineering_gateway.domain.audit import AuditEvent, AuditResult
from engineering_gateway.domain.baselines import Baseline
from engineering_gateway.domain.change_control import AuthorizationLevel, ChangeRequest
from engineering_gateway.domain.ports import AuditSink, BaselineRegistryPort, ChangeRequestRegistryPort


class ChangeRequestApplicationService:
    """Create Gateway references only after OpenProject creates the authoritative request."""

    def __init__(self, change_requests: ChangeRequestRegistryPort, openproject: OpenProjectAdapter, audit: AuditSink) -> None:
        self._change_requests = change_requests
        self._openproject = openproject
        self._audit = audit

    async def create_change_request(
        self,
        actor: Actor,
        title: str,
        description: str,
        source_baseline: Baseline | None = None,
    ) -> ChangeRequest:
        if actor.is_ai or actor.authorization_level != AuthorizationLevel.L2_MODIFY_WORKSPACE:
            raise GatewayServiceError("change-request creation requires human L2 workspace modification authority")
        try:
            external_id = await self._openproject.create_change_request(title, description)
            change_request = ChangeRequest(
                external_system=self._openproject.system_name,
                external_id=external_id,
                title=title,
                source_baseline_id=source_baseline.id if source_baseline else None,
            )
            created = await self._change_requests.create(change_request)
        except Exception as exc:
            await self._audit.record(AuditEvent(
                actor_id=actor.actor_id,
                actor_type=actor.actor_type,
                authorization_level=actor.authorization_level,
                action="create_change_request",
                target_type="change_request",
                result=AuditResult.FAILURE,
                reason=str(exc),
            ))
            if isinstance(exc, GatewayServiceError):
                raise
            raise GatewayServiceError(f"change-request creation failed: {exc}") from exc
        await self._audit.record(AuditEvent(
            actor_id=actor.actor_id,
            actor_type=actor.actor_type,
            authorization_level=actor.authorization_level,
            action="create_change_request",
            target_type="change_request",
            target_id=created.id,
            result=AuditResult.SUCCESS,
            metadata={"external_system": created.external_system, "external_id": created.external_id},
        ))
        return created


__all__ = ["ChangeRequestApplicationService"]
