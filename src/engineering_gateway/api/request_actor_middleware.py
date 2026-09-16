"""ASGI boundary that binds a trusted principal Actor to one HTTP request."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from engineering_gateway.api.actor_provider import bind_request_actor
from engineering_gateway.api.principal_mapper import PrincipalActorMapper


class TrustedPrincipalMiddleware:
    """Map claims supplied by an upstream authentication layer to a request Actor.

    The middleware deliberately does not inspect, parse, or verify bearer tokens.
    An upstream identity/authentication middleware must authenticate the request
    and place the verified claims mapping into ``scope['state']`` under the
    configured state key. This middleware only performs deterministic mapping and
    request-context binding.
    """

    def __init__(
        self,
        app: Any,
        mapper: PrincipalActorMapper,
        *,
        claims_state_key: str = "trusted_principal_claims",
    ) -> None:
        if not claims_state_key.strip():
            raise ValueError("claims_state_key must not be blank")
        self.app = app
        self.mapper = mapper
        self.claims_state_key = claims_state_key.strip()

    @property
    def router(self) -> Any:
        """Expose the wrapped router so the composition root can manage lifespan."""

        return self.app.router

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        state = scope.get("state")
        claims = state.get(self.claims_state_key) if isinstance(state, Mapping) else None
        if not isinstance(claims, Mapping):
            raise RuntimeError(
                f"trusted principal claims are missing from request state '{self.claims_state_key}'"
            )

        actor = self.mapper.map_actor(claims)
        with bind_request_actor(actor):
            await self.app(scope, receive, send)


__all__ = ["TrustedPrincipalMiddleware"]
