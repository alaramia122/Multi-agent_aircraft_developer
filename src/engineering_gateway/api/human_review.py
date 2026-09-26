"""Human-only review and approval HTTP boundary, separate from MCP."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast
from uuid import UUID

import jwt
from fastapi import FastAPI, HTTPException, Request
from jwt import PyJWKClient
from pydantic import BaseModel, Field

from engineering_gateway.application.gateway_service import Actor, GatewayServiceError
from engineering_gateway.domain.audit import ActorType
from engineering_gateway.domain.change_control import AuthorizationLevel


class ReviewDecision(BaseModel):
    accepted: bool
    reason: str = Field(min_length=1)
    evidence_uri: str = Field(min_length=1)


class Rejection(BaseModel):
    reason: str = Field(min_length=1)


class HumanTokenVerifier:
    """Verify a signed user token; service accounts and AI are never L3."""

    def __init__(self, issuer: str, audience: str, jwks_url: str, client_ids: tuple[str, ...]):
        if not issuer or not audience or not jwks_url or not client_ids:
            raise ValueError("human identity settings are required")
        self.issuer = issuer.rstrip("/")
        self.audience = audience
        self.client_ids = frozenset(client_ids)
        self.jwks = PyJWKClient(jwks_url, timeout=5)

    def verify(self, token: str) -> Actor:
        key = self.jwks.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token, key.key, algorithms=["RS256"], audience=self.audience,
            issuer=self.issuer, options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
        if claims.get("azp") not in self.client_ids:
            raise jwt.InvalidTokenError("untrusted human client")
        username = claims.get("preferred_username")
        if not isinstance(username, str) or not username or username.startswith("service-account-"):
            raise jwt.InvalidTokenError("a human user token is required")
        roles = claims.get("realm_access")
        role_names = roles.get("roles") if isinstance(roles, dict) else None
        if not isinstance(role_names, list) or not all(isinstance(role, str) for role in role_names):
            raise PermissionError("Gateway human role is required")
        granted = set(role_names)
        level = next((value for role, value in (
            ("gateway-approve", AuthorizationLevel.L3_APPROVE),
            ("gateway-modify", AuthorizationLevel.L2_MODIFY_WORKSPACE),
            ("gateway-propose", AuthorizationLevel.L1_PROPOSE),
            ("gateway-read", AuthorizationLevel.L0_READ),
        ) if role in granted), None)
        if level is None:
            raise PermissionError("Gateway human role is required")
        return Actor(actor_id=str(claims["sub"]), actor_type=ActorType.HUMAN,
                     authorization_level=level)


def create_human_review_app(service_factory: Any, verifier: HumanTokenVerifier) -> FastAPI:
    """Expose review evidence and decisions to authenticated human users only."""
    app = FastAPI(title="Engineering Gateway human review", docs_url=None, redoc_url=None, openapi_url=None)

    async def actor_for(request: Request) -> Actor:
        headers = request.scope.get("headers", ())
        values = [value for name, value in headers if name.lower() == b"authorization"]
        if len(values) != 1 or not values[0].startswith(b"Bearer "):
            raise HTTPException(401, "human bearer token required")
        try:
            token = values[0][7:].decode("ascii")
            if not token or any(character.isspace() for character in token):
                raise ValueError("malformed token")
            return await asyncio.to_thread(verifier.verify, token)
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except (UnicodeDecodeError, ValueError, jwt.PyJWTError, OSError) as exc:
            raise HTTPException(401, "invalid human bearer token") from exc

    @asynccontextmanager
    async def service() -> AsyncIterator[Any]:
        async with service_factory() as gateway:
            yield gateway

    @app.get("/workspaces/{workspace_id}")
    async def review_package(workspace_id: UUID, request: Request) -> dict[str, Any]:
        actor = await actor_for(request)
        async with service() as gateway:
            try:
                return cast(dict[str, Any], await gateway.get_workspace_review_package(actor, workspace_id))
            except GatewayServiceError as exc:
                raise HTTPException(409, str(exc)) from exc

    @app.post("/workspaces/{workspace_id}/review")
    async def independent_review(workspace_id: UUID, decision: ReviewDecision, request: Request) -> dict[str, str]:
        actor = await actor_for(request)
        async with service() as gateway:
            try:
                await gateway.record_independent_review(
                    actor, workspace_id, accepted=decision.accepted,
                    reason=decision.reason, evidence_uri=decision.evidence_uri,
                )
            except GatewayServiceError as exc:
                raise HTTPException(409, str(exc)) from exc
        return {"status": "recorded"}

    @app.post("/workspaces/{workspace_id}/approve")
    async def approve(workspace_id: UUID, request: Request) -> dict[str, str]:
        actor = await actor_for(request)
        if actor.authorization_level is not AuthorizationLevel.L3_APPROVE:
            raise HTTPException(403, "human L3 approval required")
        async with service() as gateway:
            try:
                baseline = await gateway.approve_workspace(actor, workspace_id)
            except GatewayServiceError as exc:
                raise HTTPException(409, str(exc)) from exc
        return {"baseline_id": str(baseline.id), "git_tag": baseline.git_tag}

    @app.post("/workspaces/{workspace_id}/reject")
    async def reject(workspace_id: UUID, rejection: Rejection, request: Request) -> dict[str, str]:
        actor = await actor_for(request)
        if actor.authorization_level is not AuthorizationLevel.L3_APPROVE:
            raise HTTPException(403, "human L3 approval required")
        async with service() as gateway:
            try:
                await gateway.reject_workspace(actor, workspace_id, rejection.reason)
            except GatewayServiceError as exc:
                raise HTTPException(409, str(exc)) from exc
        return {"status": "rejected"}

    return app


__all__ = ["HumanTokenVerifier", "create_human_review_app"]
