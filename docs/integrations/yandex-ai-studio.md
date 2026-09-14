# Yandex AI Studio integration

This document defines the deployment boundary between the Engineering Gateway and
Yandex AI Studio. Yandex AI Studio remains the agent/workflow orchestration layer;
engineering governance remains inside the Gateway.

## Integration shape

The Gateway exposes its governed MCP surface over **MCP Streamable HTTP**. An AI
Studio agent connects to that MCP server through the Yandex MCP integration layer.
The Gateway is responsible for authorization and deterministic governance; MCP tool
annotations are only client-facing hints.

The current Yandex documentation describes external MCP connections in AI Studio
using Streamable HTTP. Workflows can also invoke AI Studio agents through the
`AIStudioAgent` step, and a workflow can be exposed as an MCP tool through MCP Hub.

## Gateway MCP deployment contract

A deployment exposing the Gateway to AI Studio must provide:

1. A reachable Streamable HTTP endpoint, normally `/mcp`.
2. An explicit host allowlist at the MCP transport boundary.
3. Authentication at the deployment boundary appropriate to the deployment
   environment (for example, an authenticated MCP gateway or reverse proxy).
4. A fixed Gateway actor identity for the MCP endpoint. The actor's authorization
   level determines which Gateway tools are exposed.
5. No MCP tool for L3 approval or rejection. Human approval remains outside the AI
   tool surface.

The repository provides `create_mcp_http_app()` for constructing the ASGI boundary.
It requires at least one allowed host and uses the MCP SDK's DNS-rebinding/host
allowlist mechanism rather than disabling transport security.

## AI actor endpoint

The recommended first deployment is a dedicated MCP endpoint for the AI actor with
`L2_MODIFY_WORKSPACE` authorization. This allows an agent to:

- read canonical engineering data;
- run deterministic validation;
- create and modify a workspace;
- prepare a workspace for approval;
- reconcile a prepared workspace through authoritative external adapters.

It cannot approve or reject the workspace because the MCP surface intentionally does
not expose those operations.

## Workflow boundary

Yandex Workflows is used for deterministic orchestration around AI agents and
Gateway calls. Workflow inputs/outputs should carry Gateway identifiers and
references, not copies of the authoritative engineering model.

A typical flow is:

```text
AI Studio agent
      |
      | MCP / Streamable HTTP
      v
Engineering Gateway
      |
      +--> deterministic validation / change gates / audit
      |
      +--> workspace reconciliation
      |       +--> StrictDoc
      |       +--> Capella
      |       +--> OpenProject
      |
      +--> PostgreSQL metadata/state
      +--> Git baseline registry

Human L3 approval
      |
      v
Engineering Gateway approval gate
```

## Configuration boundary

AI Studio resource identifiers (agent IDs, workflow IDs, MCP registration IDs) are
deployment configuration. They are not part of the canonical engineering model and
must not become a second source of engineering truth in PostgreSQL.

Secrets and service-account credentials must likewise remain outside the repository
and be supplied by the deployment environment.

## Current Yandex-specific constraints

As of September 2026, Yandex documentation states that Workflows created in the AI
Studio UI are managed there; Workflows created in the Yandex Cloud UI were made
available in AI Studio, while creation/management in the Yandex Cloud UI is being
retired. Therefore new workflow definitions should be treated as AI Studio
configuration rather than as a Gateway runtime dependency.
