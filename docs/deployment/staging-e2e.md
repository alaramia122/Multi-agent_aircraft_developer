# Staging / E2E runbook

## Scope

The staging slice verifies the Gateway deployment boundary before Yandex AI Studio is connected.

It deliberately separates two levels:

1. **Core staging E2E** — reproducible in CI without customer credentials.
2. **External integration staging** — requires real Git, StrictDoc, Capella, OpenProject, identity and object-storage endpoints.

## Core staging stack

```text
docker-compose.staging.yml

PostgreSQL
    |
    v
migration job
    |
    v
Gateway
    |
    +--> /health/live
    |
    +--> /health/ready
    |
    +--> /mcp
```

The Gateway container receives the repository as a read-only mount so the Git readiness boundary can verify the actual `.git` directory. PostgreSQL migrations are executed by a dedicated one-shot container before the Gateway starts.

The core stack intentionally keeps StrictDoc, Capella, OpenProject and Object Storage disabled. Readiness reports them as `disabled`; it must not silently report them as healthy integrations.

## Run locally

Set a staging database password:

```bash
export POSTGRES_PASSWORD=change-me
docker compose -f docker-compose.staging.yml up --build --detach
```

Check the service:

```bash
curl http://127.0.0.1:8000/health/live
curl http://127.0.0.1:8000/health/ready
python scripts/staging_smoke.py
```

Stop and remove the staging database:

```bash
docker compose -f docker-compose.staging.yml down --volumes
```

## Core acceptance gate

The smoke test requires:

- HTTP liveness returns 200;
- readiness returns 200 and `status=ready`;
- PostgreSQL is ready at schema version 14;
- Git repository readiness is `ready`;
- optional external integrations are explicitly `disabled`.

This proves the deployable Gateway can start with its database and repository boundary rather than only passing in-process tests.

## External integration stage

The selected external staging target is one Yandex Cloud VM. The reproducible
topology, secret/DNS prerequisites and bootstrap procedure are in
`deploy/yandex-vm/README.md`. The Gateway is reachable only through Caddy and
OAuth2 Proxy; its container port is not published.

The next staging environment must enable integrations one at a time:

1. identity provider / trusted-principal boundary;
2. Git repository and server-side branch/tag policy;
3. StrictDoc project and CLI;
4. Capella headless bridge;
5. OpenProject API v3;
6. Object Storage.

For every enabled integration, readiness must become `ready`. Contract tests must then verify the adapter-specific protocol, malformed-response handling, optimistic locking and idempotency.

Only after these checks should the full governed reconciliation scenario be executed against staging systems.

## E2E scenarios

### Identity

Verify at least:

- L0 request can read;
- L1 request can propose;
- L2 request can mutate/reconcile a workspace;
- L2 cannot approve;
- AI + L3 mapping is rejected;
- two concurrent requests retain separate Actors;
- missing trusted claims fail closed.

### Governance

Verify:

```text
Change Request
  -> ACTIVE workspace
  -> deterministic validation
  -> READY_FOR_APPROVAL
  -> reconciliation
  -> human L3 approval
  -> immutable baseline
```

Also verify that an approved workspace cannot be modified and that replaying the same change-set does not duplicate external effects.

### External systems

The staging E2E must use the authoritative external systems rather than replacing them with Gateway database records:

- StrictDoc for requirements;
- Capella for architecture;
- OpenProject for Change Request;
- Git for baseline provenance.

## Current boundary

The repository now contains the reproducible core staging stack, CI smoke gate, and a composition root that wires every enabled local external adapter into the Gateway service. StrictDoc, Capella and OpenProject remain disabled in the core stack, so their real protocols are not exercised by the core smoke run. This does **not** claim that customer-specific external systems or a production IdP are available.

The remaining work after the core staging gate is to supply deployment-specific endpoints/credentials and execute the external integration E2E. Before that, adapter contract tests should be run against deterministic local fixtures where the real systems are not yet available.
