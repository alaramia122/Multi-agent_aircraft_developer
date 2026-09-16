"""Trusted actor provisioning boundary for Gateway transports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from engineering_gateway.application.gateway_service import Actor


class ActorProvider(Protocol):
    """Resolve the already-authenticated deployment principal to a Gateway actor."""

    def get_actor(self) -> Actor:
        """Return the trusted actor for this Gateway endpoint/session."""


@dataclass(frozen=True)
class StaticActorProvider:
    """Provide a fixed actor for a single-purpose trusted deployment."""

    actor: Actor

    def get_actor(self) -> Actor:
        return self.actor


__all__ = ["ActorProvider", "StaticActorProvider"]
