# Production Identity Boundary

## Purpose

This document defines the deployment contract between an upstream authentication layer and the Engineering Gateway identity boundary.

The Gateway receives an already authenticated principal. It does not authenticate bearer tokens, verify JWT signatures, validate issuers or audiences, or implement an OIDC provider. Authentication and token verification remain deployment concerns.

## Trust boundary

```text
External IdP / authentication middleware
        |
        | authenticate and verify principal
        | write verified claims to ASGI request state
        v
scope["state"]["trusted_principal_claims"]
        |
        v
TrustedPrincipalMiddleware
        |
        | ClaimMapping
        v
Gateway Actor
        |
        v
RequestActorProvider
        |
        v
MCP tool invocation
        |
        v
Gateway authorization
```

`TrustedPrincipalMiddleware` is a trust-boundary adapter, not an authentication mechanism. It is safe to consume the claims state only when the deployment guarantees that the middleware runs after the verified authentication boundary and that the configured state key cannot be populated by untrusted request data.

The default state key is `trusted_principal_claims`; deployments may configure another key through `IDENTITY__PRINCIPAL_CLAIMS_STATE_KEY`.

## Upstream authentication contract

The upstream authentication layer MUST:

1. authenticate the incoming principal;
2. verify the credentials/token according to the selected IdP protocol;
3. establish issuer/audience and other deployment-specific token validity requirements;
4. construct the claims mapping from the verified identity;
5. place that mapping in `scope["state"]` under the configured trusted-claims state key;
6. reject or otherwise terminate unauthenticated requests before they reach the Gateway MCP application.

The Gateway assumes these conditions. The claims mapping is therefore not an authorization credential by itself; it is trusted only because of its position behind the deployment authentication boundary.

The Gateway MUST NOT treat raw HTTP headers, query parameters, MCP arguments, model output, or unverified bearer-token data as a trusted principal.

## Claims contract

The default mapping is:

| Gateway field | Default claim | Required value |
|---|---|---|
| `Actor.actor_id` | `sub` | non-blank string |
| `Actor.actor_type` | `actor_type` | string accepted by Gateway `ActorType` |
| `Actor.authorization_level` | `authorization_level` | string accepted by Gateway `AuthorizationLevel` |

Claim names are deployment configuration and can be changed independently:

```text
IDENTITY__ACTOR_ID_CLAIM
IDENTITY__ACTOR_TYPE_CLAIM
IDENTITY__AUTHORIZATION_LEVEL_CLAIM
IDENTITY__PRINCIPAL_CLAIMS_STATE_KEY
```

All three Actor claims are mandatory for the mapper. Values must be strings; blank strings are rejected. Unknown `ActorType` or `AuthorizationLevel` values are rejected rather than coerced or downgraded.

Missing or malformed trusted claims are a failed identity mapping and MUST NOT produce an Actor.

## Actor and authorization

The mapper produces the existing Gateway `Actor` domain object. It does not introduce a second authorization model.

Authorization levels remain:

- `L0_READ` — read operations;
- `L1_PROPOSE` — proposal operations;
- `L2_MODIFY_WORKSPACE` — workspace mutation and reconciliation;
- `L3_APPROVE` — human approval only.

MCP annotations are metadata and do not grant these permissions. Each governed operation resolves the current Actor and performs authorization at invocation time.

AI principals MUST NOT be assigned L3. Approval and rejection are not exposed through the MCP tool surface.

## Request-scoped identity

A production MCP application is long-lived, while individual HTTP requests may belong to different principals. Therefore an Actor MUST NOT be captured when the MCP server or FastAPI application is created.

The deployment uses `RequestActorProvider` backed by a request execution context. `TrustedPrincipalMiddleware` binds the mapped Actor only for the duration of the current HTTP request and restores the previous context afterwards.

Consequently:

- sequential requests may resolve to different Actors;
- concurrent requests must retain their own Actor context;
- after request completion, the Actor is not available through the request provider;
- application startup and shutdown do not establish an Actor.

## MCP and ASGI lifecycle

`TrustedPrincipalMiddleware` wraps the Streamable HTTP MCP application. Non-HTTP ASGI scopes, including `lifespan`, are passed through to the wrapped application.

The composition root owns the process-level database resource and preserves the wrapped MCP router lifecycle. The identity middleware itself does not create or destroy MCP resources.

The deployment must verify that startup, shutdown, Streamable HTTP handling and the configured MCP mount continue to work when the identity wrapper is enabled.

## Failure modes

| Condition | Required behavior |
|---|---|
| Trusted claims state is absent | request fails closed; no Actor is bound |
| Trusted claims state is not a mapping | request fails closed; no Actor is bound |
| Required claim is absent | mapping fails; no Actor is produced |
| Required claim is non-string/blank | mapping fails; no Actor is produced |
| Unknown `ActorType` | mapping fails; no Actor is produced |
| Unknown `AuthorizationLevel` | mapping fails; no Actor is produced |
| Unverified principal data reaches the state key | deployment configuration is invalid; it MUST NOT be treated as trusted |
| Actor context exits request | context is restored/cleared |
| L0/L1 attempts L2 operation | Gateway authorization denies the operation |
| L2 attempts approval | approval remains unavailable |
| AI principal is assigned L3 | deployment MUST reject that mapping; AI cannot receive approval capability |

The exact HTTP error representation is a transport/application concern; the security property is fail-closed behavior and absence of an unauthorized Actor.

## Why the Gateway does not verify JWT/OIDC

Authentication is a deployment boundary. The Gateway's responsibility begins with a trusted principal and ends with deterministic mapping and authorization against Gateway capabilities.

Keeping token verification outside the Gateway avoids coupling the engineering governance core to a particular IdP or token protocol. It also makes the trust boundary explicit: a deployment either supplies verified claims or the Gateway has no principal to authorize.

If a future deployment requires Gateway-local token verification, that is a separate architectural decision and must not be introduced implicitly into this mapper/middleware contract.

## Configuration

The identity configuration is supplied through typed environment variables:

```text
IDENTITY__ENABLED
IDENTITY__ISSUER_URL
IDENTITY__AUDIENCE
IDENTITY__ACTOR_ID_CLAIM
IDENTITY__ACTOR_TYPE_CLAIM
IDENTITY__AUTHORIZATION_LEVEL_CLAIM
IDENTITY__PRINCIPAL_CLAIMS_STATE_KEY
```

When identity is enabled, `IDENTITY__ISSUER_URL` and `IDENTITY__AUDIENCE` are required configuration values. They describe the expected deployment identity provider and audience; the current Gateway does not itself perform the corresponding token verification.

Claim names and the trusted-claims state key must be non-blank.

## Readiness and rollout

Identity readiness MUST remain `NOT READY` until a real upstream authentication layer and trusted principal-to-Actor mapping are deployed.

The production rollout order is:

1. deploy PostgreSQL and required migrations;
2. deploy the Gateway with identity disabled while transport/dependency readiness is established;
3. deploy the upstream authentication boundary;
4. configure and validate the trusted claims state contract;
5. enable Gateway identity mapping;
6. verify readiness and HTTP/MCP authorization with multiple principals;
7. run staging reconciliation and governance tests;
8. only then expose the MCP endpoint to Yandex AI Studio.

A static development Actor is retained only for the explicitly configured non-identity deployment mode. It must not be mistaken for production authentication.

## Security requirements

Production deployments MUST:

- place the trusted-principal middleware after verified authentication;
- prevent clients from directly writing the trusted claims state;
- use TLS and deployment-appropriate transport protection;
- restrict MCP hosts/origins to the intended deployment;
- keep IdP credentials and secrets outside the repository;
- audit denied and failed governed operations using the Gateway audit boundary;
- test request isolation with sequential and concurrent principals;
- keep L3 approval outside MCP and restricted to human actors.

The identity layer is an input boundary. Governance remains enforced by the Gateway services and is never delegated to prompts, MCP annotations, or claims alone.
