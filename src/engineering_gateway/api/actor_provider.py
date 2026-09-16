"""Trusted actor provisioning boundaries for Gateway transports."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator, Protocol

from engineering_gateway.application.gateway_service import Actor


class ActorProvider(Protocol):
    """Resolve the already-authenticated deployment principal to a Gateway actor."""

    def get_actor(self) -> Actor:
        """Return the trusted actor for the current request/operation."""


@dataclass(frozen=True)
class StaticActorProvider:
    """Provide a fixed actor for a single-purpose trusted deployment."""

    actor: Actor

    def get_actor(self) -> Actor:
        return self.actor


_request_actor: ContextVar[Actor | None] = ContextVar("engineering_gateway_request_actor", default=None)


@dataclass(frozen=True)
class RequestActorProvider:
    """Resolve the actor from the current request execution context."""

    def get_actor(self) -> Actor:
        actor = _request_actor.get()
        if actor is None:
            raise RuntimeError("no trusted Actor is bound to the current request")
        return actor


@contextmanager
def bind_request_actor(actor: Actor) -> Iterator[None]:
    """Bind a trusted actor for the duration of one request context."""

    token = _request_actor.set(actor)
    try:
        yield
    finally:
        _request_actor.reset(token)


__all__ = ["ActorProvider", "RequestActorProvider", "StaticActorProvider", "bind_request_actor"]
