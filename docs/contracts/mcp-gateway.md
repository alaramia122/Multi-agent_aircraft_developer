# MCP Gateway Contract

## Purpose

MCP is the external tool boundary of the Engineering Gateway. It is not a second governance layer and does not contain standard-specific compliance rules.

The MCP server delegates operations to Gateway application services. Gateway authorization and deterministic validation remain authoritative.

## External tool boundary

When the Tool Invocation Service is configured, MCP exposes:

- `list_available_tools` — deterministic discovery from the Tool Registry;
- `invoke_engineering_tool` — execution through Tool Policy and a registered adapter.

The invocation receives the current request-scoped Actor. Client-supplied actor identity or authorization is never trusted. Tool trust, operation permission, project scope and side-effect policy are rechecked immediately before execution.

For AI actors, the MCP boundary cannot lower the minimum trust below SANDBOX. PHYSICAL operations remain blocked until a dedicated safety gate exists.

## Existing Gateway tools

### Read-capable actors

- `get_engineering_element`
- `get_engineering_relations`
- `validate_engineering_graph`

### L2 workspace actors

- `create_workspace`
- `save_workspace_element`
- `add_workspace_relation`
- `prepare_workspace_for_approval`
- `reconcile_workspace`

These mutation tools remain governed by the existing L2 boundary.

## Approval boundary

No MCP actor receives `approve_workspace` or `reject_workspace`. Human L3 approval is an application-service operation outside the AI tool surface.

MCP annotations are descriptive metadata and never replace Gateway authorization.

## Data authority

MCP does not read PostgreSQL, Git, StrictDoc, Capella or OpenProject directly. Those systems remain behind Gateway adapters.

## Identity

The MCP composition receives an already-authenticated Gateway `Actor`. The transport/integration layer establishes that identity; Gateway checks its authorization level and actor type.
