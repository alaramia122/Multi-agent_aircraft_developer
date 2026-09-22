"""Trusted reverse-proxy headers to verified-principal ASGI state adapter."""

from __future__ import annotations

import hmac
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TrustedProxyHeaderConfig:
    """Header contract used only on a network-isolated proxy hop."""

    shared_secret: str
    claims_state_key: str = "trusted_principal_claims"
    secret_header: str = "x-gateway-proxy-secret"
    actor_id_header: str = "x-gateway-actor-id"
    actor_type_header: str = "x-gateway-actor-type"
    authorization_level_header: str = "x-gateway-authorization-level"
    actor_id_claim: str = "sub"
    actor_type_claim: str = "actor_type"
    authorization_level_claim: str = "authorization_level"

    def __post_init__(self) -> None:
        if len(self.shared_secret) < 32:
            raise ValueError("shared_secret must contain at least 32 characters")
        for name, value in (
            ("shared_secret", self.shared_secret),
            ("claims_state_key", self.claims_state_key),
            ("secret_header", self.secret_header),
            ("actor_id_header", self.actor_id_header),
            ("actor_type_header", self.actor_type_header),
            ("authorization_level_header", self.authorization_level_header),
            ("actor_id_claim", self.actor_id_claim),
            ("actor_type_claim", self.actor_type_claim),
            ("authorization_level_claim", self.authorization_level_claim),
        ):
            if not value.strip():
                raise ValueError(f"{name} must not be blank")


class TrustedProxyPrincipalMiddleware:
    """Translate authenticated proxy headers into trusted request state.

    This middleware does not authenticate an end-user token. It authenticates one
    internal reverse-proxy hop with a deployment secret, rejects duplicate or
    missing identity headers, removes the trusted headers, and then supplies the
    verified-principal state expected by :class:`TrustedPrincipalMiddleware`.

    It is safe only when the Gateway listener is not directly reachable by clients
    and the reverse proxy overwrites every trusted header.
    """

    def __init__(self, app: Any, config: TrustedProxyHeaderConfig) -> None:
        self.app = app
        self.config = config
        self._trusted_headers = {
            config.secret_header.lower(),
            config.actor_id_header.lower(),
            config.actor_type_header.lower(),
            config.authorization_level_header.lower(),
        }

    @property
    def router(self) -> Any:
        """Expose the wrapped router so the composition root can manage lifespan."""

        return self.app.router

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        headers = self._decode_headers(scope.get("headers", ()))
        supplied_secret = self._required_single_header(headers, self.config.secret_header)
        if not hmac.compare_digest(supplied_secret, self.config.shared_secret):
            raise RuntimeError("trusted proxy authentication failed")

        claims = {
            self.config.actor_id_claim: self._required_single_header(
                headers, self.config.actor_id_header
            ),
            self.config.actor_type_claim: self._required_single_header(
                headers, self.config.actor_type_header
            ),
            self.config.authorization_level_claim: self._required_single_header(
                headers, self.config.authorization_level_header
            ),
        }

        state = scope.get("state")
        if state is None:
            trusted_state: dict[str, Any] = {}
        elif isinstance(state, Mapping):
            trusted_state = dict(state)
        else:
            raise RuntimeError("ASGI request state must be a mapping")
        if self.config.claims_state_key in trusted_state:
            raise RuntimeError("trusted principal state is already populated")
        trusted_state[self.config.claims_state_key] = claims

        trusted_scope = dict(scope)
        trusted_scope["state"] = trusted_state
        trusted_scope["headers"] = [
            (name, value)
            for name, value in scope.get("headers", ())
            if name.decode("latin-1").lower() not in self._trusted_headers
        ]
        await self.app(trusted_scope, receive, send)

    @staticmethod
    def _decode_headers(raw_headers: Any) -> dict[str, list[str]]:
        decoded: dict[str, list[str]] = {}
        try:
            for raw_name, raw_value in raw_headers:
                name = raw_name.decode("latin-1").lower()
                value = raw_value.decode("utf-8").strip()
                decoded.setdefault(name, []).append(value)
        except (AttributeError, UnicodeDecodeError, ValueError) as exc:
            raise RuntimeError("request headers are malformed") from exc
        return decoded

    @staticmethod
    def _required_single_header(headers: Mapping[str, list[str]], name: str) -> str:
        values = headers.get(name.lower(), [])
        if len(values) != 1 or not values[0]:
            raise RuntimeError(f"trusted proxy header '{name}' must occur exactly once")
        return values[0]


__all__ = ["TrustedProxyHeaderConfig", "TrustedProxyPrincipalMiddleware"]
