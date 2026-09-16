# MCP actor provisioning contract

## Purpose

The MCP transport is not an authentication or authorization authority. It receives an already authenticated Gateway `Actor` from the deployment boundary and passes that identity unchanged to the application service.

## Required boundary

A production HTTP deployment MUST provision the `Actor` from an authenticated external identity before invoking `create_mcp_http_app()` or an equivalent request/session integration.

The deployment layer is responsible for:

- authenticating the caller;
- resolving a stable `actor_id` from the authenticated identity;
- determining `ActorType` from trusted identity/configuration, not MCP tool arguments;
- determining the maximum `AuthorizationLevel` from trusted server-side policy;
- rejecting an identity when no Gateway authorization mapping exists.

The MCP client MUST NOT be able to supply or override these fields through tool arguments, MCP metadata, tool annotations, or prompt content.

## Gateway enforcement

The Gateway remains authoritative even when MCP is used:

- L0/L1 actors can use the read surface;
- L2 is required for workspace mutation;
- L3 approval is a human-only application operation;
- approval and rejection are not exposed as MCP tools;
- MCP `ToolAnnotations` are descriptive metadata and MUST NOT be treated as an authorization mechanism.

A deployment that supplies a fixed `Actor` to `create_mcp_http_app()` therefore creates a fixed-identity MCP endpoint. This is acceptable for a single-purpose trusted service identity, but a multi-user deployment MUST resolve identity at its authenticated request/session boundary rather than deriving it from MCP input.

## Non-goals

This contract does not prescribe a particular authentication technology (OAuth, mTLS, reverse-proxy authentication, service-account credentials, etc.). The concrete mechanism belongs to the deployment environment; the resulting trusted identity-to-Actor mapping is the invariant required by the Gateway.
