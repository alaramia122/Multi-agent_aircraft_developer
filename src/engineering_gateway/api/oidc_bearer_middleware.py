"""Verify Keycloak access tokens before binding an MCP request principal."""

from __future__ import annotations

import asyncio
import hmac
import json
from collections.abc import Mapping, Sequence
from typing import Any

import jwt
from jwt import PyJWKClient

from engineering_gateway.domain.change_control import AuthorizationLevel


class OidcBearerPrincipalMiddleware:
    """Authenticate one bounded service-account token against a pinned OIDC issuer.

    Capabilities come only from signed realm roles. Client credentials can never
    become a human approver, even if an IdP administrator assigns an L3 role.
    """

    def __init__(
        self,
        app: Any,
        *,
        issuer: str,
        audience: str,
        jwks_url: str,
        allowed_client_ids: Sequence[str],
        claims_state_key: str = "trusted_principal_claims",
        actor_id_claim: str = "sub",
        actor_type_claim: str = "actor_type",
        authorization_level_claim: str = "authorization_level",
        mcp_service_token: str | None = None,
        mcp_service_actor_id: str = "yandex-ai-studio",
        mcp_service_authorization_level: AuthorizationLevel = AuthorizationLevel.L2_MODIFY_WORKSPACE,
    ) -> None:
        if not all((issuer, audience, jwks_url, claims_state_key, *allowed_client_ids)):
            raise ValueError("OIDC issuer, audience, keys, state and clients must be configured")
        self.app = app
        self.issuer = issuer.rstrip("/")
        self.audience = audience
        self.allowed_client_ids = frozenset(allowed_client_ids)
        self.jwks = PyJWKClient(jwks_url, timeout=5)
        self.claims_state_key = claims_state_key
        self.actor_id_claim = actor_id_claim
        self.actor_type_claim = actor_type_claim
        self.authorization_level_claim = authorization_level_claim
        if mcp_service_token is not None and len(mcp_service_token) < 32:
            raise ValueError("MCP service token must contain at least 32 characters")
        if mcp_service_authorization_level is AuthorizationLevel.L3_APPROVE:
            raise ValueError("machine credentials cannot grant approval")
        self.mcp_service_token = mcp_service_token
        self.mcp_service_actor_id = mcp_service_actor_id
        self.mcp_service_authorization_level = mcp_service_authorization_level

    @property
    def router(self) -> Any:
        return self.app.router

    def _verify(self, token: str) -> dict[str, str]:
        if self.mcp_service_token is not None and hmac.compare_digest(
            token, self.mcp_service_token
        ):
            return {
                self.actor_id_claim: self.mcp_service_actor_id,
                self.actor_type_claim: "ai",
                self.authorization_level_claim: self.mcp_service_authorization_level.value,
            }
        key = self.jwks.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            audience=self.audience,
            issuer=self.issuer,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
        client_id = claims.get("azp")
        if not isinstance(client_id, str) or client_id not in self.allowed_client_ids:
            raise jwt.InvalidTokenError("untrusted client")
        if claims.get("preferred_username") != f"service-account-{client_id}":
            raise jwt.InvalidTokenError("only service accounts may use this MCP endpoint")
        roles = claims.get("realm_access")
        role_names = roles.get("roles") if isinstance(roles, dict) else None
        if not isinstance(role_names, list) or not all(isinstance(role, str) for role in role_names):
            raise PermissionError("no valid Gateway roles in access token")
        granted = set(role_names)
        if "gateway-approve" in granted:
            raise PermissionError("AI service accounts cannot receive approval authority")
        level = next(
            (
                level for role, level in (
                    ("gateway-modify", "L2_MODIFY_WORKSPACE"),
                    ("gateway-propose", "L1_PROPOSE"),
                    ("gateway-read", "L0_READ"),
                )
                if role in granted
            ),
            None,
        )
        if level is None:
            raise PermissionError("Gateway role is required")
        return {
            self.actor_id_claim: str(claims["sub"]),
            self.actor_type_claim: "ai",
            self.authorization_level_claim: level,
        }

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        raw_headers = scope.get("headers", ())
        authorization = [
            value for name, value in raw_headers if name.lower() == b"authorization"
        ]
        if len(authorization) != 1 or not authorization[0].startswith(b"Bearer "):
            await self._deny(send, 401)
            return
        try:
            token = authorization[0][7:].decode("ascii")
            if not token or any(character.isspace() for character in token):
                raise ValueError("invalid bearer token")
            claims = await asyncio.to_thread(self._verify, token)
        except PermissionError:
            await self._deny(send, 403)
            return
        except (UnicodeDecodeError, ValueError, jwt.PyJWTError, OSError):
            await self._deny(send, 401)
            return

        state = scope.get("state")
        if state is not None and not isinstance(state, Mapping):
            await self._deny(send, 401)
            return
        trusted_state = dict(state or {})
        if self.claims_state_key in trusted_state:
            await self._deny(send, 401)
            return
        trusted_state[self.claims_state_key] = claims
        trusted_scope = dict(scope)
        trusted_scope["state"] = trusted_state
        trusted_scope["headers"] = [
            (name, value) for name, value in raw_headers if name.lower() != b"authorization"
        ]
        await self.app(trusted_scope, receive, send)

    @staticmethod
    async def _deny(send: Any, status: int) -> None:
        body = json.dumps({"error": "forbidden" if status == 403 else "unauthorized"}).encode()
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"www-authenticate", b"Bearer"),
            ],
        })
        await send({"type": "http.response.body", "body": body})


__all__ = ["OidcBearerPrincipalMiddleware"]
