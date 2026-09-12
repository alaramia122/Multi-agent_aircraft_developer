"""Governed application operations for Standard Profile lifecycle."""

from engineering_gateway.application.gateway_service import Actor, GatewayServiceError
from engineering_gateway.application.profile_engine import ProfileCompositionError, StandardProfileEngine
from engineering_gateway.domain.audit import AuditEvent, AuditResult
from engineering_gateway.domain.change_control import AuthorizationLevel
from engineering_gateway.domain.ports import AuditSink, StandardProfileRegistry
from engineering_gateway.domain.profiles import StandardProfile
from uuid import uuid4


class StandardProfileApplicationService:
    """Application boundary for immutable profile registration and activation."""

    def __init__(self, registry: StandardProfileRegistry, audit: AuditSink) -> None:
        self._registry = registry
        self._audit = audit

    async def register(self, actor: Actor, profile: StandardProfile) -> None:
        if actor.is_ai or actor.authorization_level != AuthorizationLevel.L3_APPROVE:
            raise GatewayServiceError("Standard Profile registration requires a human L3 governance actor")
        try:
            StandardProfileEngine.validate_profile(profile)
            await self._registry.register(profile)
        except (ValueError, ProfileCompositionError) as exc:
            await self._record(actor, "register_profile", profile, AuditResult.FAILURE, str(exc))
            raise GatewayServiceError(str(exc)) from exc
        await self._record(actor, "register_profile", profile, AuditResult.SUCCESS)

    async def activate(self, actor: Actor, profile_id: str, version: str) -> StandardProfile:
        if actor.is_ai or actor.authorization_level != AuthorizationLevel.L3_APPROVE:
            raise GatewayServiceError("Standard Profile activation requires a human L3 governance actor")
        try:
            profile = await self._registry.activate(profile_id, version)
        except ValueError as exc:
            await self._record_identity(actor, "activate_profile", profile_id, version, AuditResult.FAILURE, str(exc))
            raise GatewayServiceError(str(exc)) from exc
        await self._record_identity(actor, "activate_profile", profile_id, version, AuditResult.SUCCESS)
        return profile

    async def deactivate(self, actor: Actor, profile_id: str, version: str) -> None:
        if actor.is_ai or actor.authorization_level != AuthorizationLevel.L3_APPROVE:
            raise GatewayServiceError("Standard Profile deactivation requires a human L3 governance actor")
        try:
            await self._registry.deactivate(profile_id, version)
        except ValueError as exc:
            await self._record_identity(actor, "deactivate_profile", profile_id, version, AuditResult.FAILURE, str(exc))
            raise GatewayServiceError(str(exc)) from exc
        await self._record_identity(actor, "deactivate_profile", profile_id, version, AuditResult.SUCCESS)

    async def compose(self, actor: Actor, profiles: list[StandardProfile], *, profile_id: str, version: str, name: str) -> StandardProfile:
        if actor.is_ai or actor.authorization_level != AuthorizationLevel.L3_APPROVE:
            raise GatewayServiceError("Standard Profile composition requires a human L3 governance actor")
        try:
            composed = StandardProfileEngine.compose(profiles, id=profile_id, version=version, name=name)
            await self._registry.register(composed)
        except (ValueError, ProfileCompositionError) as exc:
            await self._record_identity(actor, "compose_profile", profile_id, version, AuditResult.FAILURE, str(exc))
            raise GatewayServiceError(str(exc)) from exc
        await self._record_identity(actor, "compose_profile", profile_id, version, AuditResult.SUCCESS)
        return composed

    async def _record(self, actor: Actor, action: str, profile: StandardProfile, result: AuditResult, reason: str | None = None) -> None:
        await self._record_identity(actor, action, profile.id, profile.version, result, reason)

    async def _record_identity(self, actor: Actor, action: str, profile_id: str, version: str, result: AuditResult, reason: str | None = None) -> None:
        await self._audit.record(AuditEvent(
            actor_id=actor.actor_id,
            actor_type=actor.actor_type,
            authorization_level=actor.authorization_level,
            action=action,
            target_type="standard_profile",
            result=result,
            reason=reason,
            correlation_id=uuid4(),
            metadata={"profile_id": profile_id, "profile_version": version},
        ))


__all__ = ["StandardProfileApplicationService"]
