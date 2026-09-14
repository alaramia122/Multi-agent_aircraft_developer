# MCP Gateway Contract

## Purpose

MCP is the external tool boundary of the Engineering Gateway. It is not a second governance layer and does not contain standard-specific compliance rules.

The MCP server delegates operations to the Gateway application services. Gateway authorization and deterministic validation remain authoritative.

## Tool classes

### Read-capable actors

- `get_engineering_element`
- `get_engineering_relations`
- `validate_engineering_graph`

### L2 workspace actors

In addition to the read/validation tools:

- `create_workspace`
- `save_workspace_element`
- `add_workspace_relation`
- `prepare_workspace_for_approval`
- `reconcile_workspace`

The mutation tools are intentionally scoped to workspace state. Reconciliation publishes a prepared workspace to configured authoritative external systems and remains an L2 operation.

### Approval boundary

No MCP actor receives `approve_workspace` or `reject_workspace`. Human L3 approval is an application-service operation outside the AI tool surface.

The absence of a tool is not the only security mechanism: the application service also rejects unauthorized calls. MCP annotations are descriptive metadata and never replace Gateway authorization.

## Data authority

MCP returns Gateway/domain representations and deterministic validation results. It does not read PostgreSQL, Git, StrictDoc, Capella or OpenProject directly. Those systems remain behind the Gateway and their adapters.

## Identity

The MCP composition receives an already-authenticated Gateway `Actor`. The transport/integration layer is responsible for establishing that identity; the Gateway is responsible for checking its authorization level and actor type.

The infrastructure does not assume a particular AI provider or embed provider-specific authentication logic in the domain/application layers.
