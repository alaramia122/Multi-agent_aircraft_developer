"""Deployment-side principal-to-Actor mapping contract.

Authentication is intentionally outside the Gateway core. A deployment may
verify a principal with its identity provider and then pass the trusted
principal claims to this mapper. Unverified request data must never be used
as an Actor directly.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, TypeVar

from engineering_gateway.application.gateway_service import Actor
from engineering_gateway.domain.audit import ActorType
from engineering_gateway.domain.change_control import AuthorizationLevel


class PrincipalActorMapper(Protocol):
    """Map an already-authenticated principal to a Gateway Actor."""

    def map_actor(self, claims: Mapping[str, object]) -> Actor:
        """Return the trusted actor represented by verified principal claims."""


@dataclass(frozen=True)
class ClaimMapping:
    """Names of claims supplied by the deployment identity layer."""

    actor_id_claim: str = "sub"
    actor_type_claim: str = "actor_type"
    authorization_level_claim: str = "authorization_level"


EnumT = TypeVar("EnumT", bound=Enum)


@dataclass(frozen=True)
class TrustedClaimsActorMapper:
    """Deterministically map verified claims to an Actor.

    This class does not authenticate tokens, validate signatures, issuers or
    audiences. Those responsibilities belong to deployment identity
    middleware. Only that trusted layer should call ``map_actor``.
    """

    mapping: ClaimMapping = ClaimMapping()

    def map_actor(self, claims: Mapping[str, object]) -> Actor:
        actor_id = self._required_string(claims, self.mapping.actor_id_claim)
        actor_type = self._enum_value(claims, self.mapping.actor_type_claim, ActorType)
        authorization_level = self._enum_value(
            claims, self.mapping.authorization_level_claim, AuthorizationLevel
        )
        if actor_type is ActorType.AI and authorization_level is AuthorizationLevel.L3_APPROVE:
            raise ValueError("AI actors cannot be assigned L3_APPROVE")
        return Actor(
            actor_id=actor_id,
            actor_type=actor_type,
            authorization_level=authorization_level,
        )

    @staticmethod
    def _required_string(claims: Mapping[str, object], claim: str) -> str:
        value = claims.get(claim)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"trusted identity claim '{claim}' must be a non-blank string")
        return value.strip()

    @staticmethod
    def _enum_value(
        claims: Mapping[str, object], claim: str, enum_type: type[EnumT]
    ) -> EnumT:
        value = TrustedClaimsActorMapper._required_string(claims, claim)
        try:
            return enum_type(value)
        except ValueError as exc:
            raise ValueError(f"unsupported value for trusted identity claim '{claim}'") from exc


__all__ = ["ClaimMapping", "PrincipalActorMapper", "TrustedClaimsActorMapper"]
