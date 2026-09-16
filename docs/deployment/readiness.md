# Deployment and readiness

## Deployment contract

The repository now contains a minimal container deployment for the Gateway:

- `Dockerfile` builds the application image from Python 3.12;
- the image runs as an unprivileged `gateway` user;
- `docker-compose.yml` provides a PostgreSQL + Gateway staging composition;
- production credentials remain deployment inputs and are not baked into the image.

The compose file is a reproducible staging/local reference, not a claim that customer-specific identity, StrictDoc, Capella, OpenProject or object storage services are available.

## Database initialization

The repository uses the migration order documented in `migrations/README.md`:

1. apply `migrations/versions/*.sql` in lexical order;
2. apply `migrations/*.sql` in lexical order;
3. verify that migration `0014_deployment_readiness_schema.sql` created `gateway_schema_version` with version `14`.

Migration execution remains an explicit deployment operation. The Gateway does not mutate the production schema implicitly during application startup.

## Health endpoints

### Liveness

`GET /health/live` answers only whether the process is serving HTTP. It does not access PostgreSQL or external systems and should be used by container/process liveness probes.

`GET /health` remains a compatibility alias for the same process-level check.

### Readiness

`GET /health/ready` checks:

- PostgreSQL connectivity;
- the exact Gateway schema marker version;
- Git repository availability when Git is enabled;
- StrictDoc executable and project path when enabled;
- Capella bridge executable and project path when enabled;
- OpenProject endpoint reachability when enabled;
- object-storage endpoint reachability when enabled;
- the identity boundary.

A disabled optional integration is reported as `disabled`, not as a successful integration probe. An enabled dependency that cannot satisfy its check makes the endpoint return HTTP `503`.

The response is deliberately structured and stable:

```json
{
  "status": "ready",
  "checks": [
    {"name": "postgresql", "status": "ready", "detail": "schema version 14"},
    {"name": "identity", "status": "disabled", "detail": "external identity mapping is disabled"}
  ]
}
```

Readiness never returns credentials, tokens, request payloads or external system data.

## Identity safety boundary

The current application composition still uses the static Actor provider. Therefore enabling `IDENTITY__ENABLED=true` makes readiness fail until a trusted principal-to-Actor mapper is wired into the composition root.

This is intentional: an enabled identity configuration must not create the false impression that authenticated principals are actually being mapped to Gateway Actors.

AI principals must not receive `L3_APPROVE`; approval/rejection remains outside MCP.

## External integration semantics

The readiness layer verifies deployment prerequisites and contract-level reachability. It does not replace adapter protocol validation or an end-to-end staging contract test.

In particular:

- Git readiness checks repository availability, while Git adapter operations remain authoritative for snapshots and ancestry;
- StrictDoc/Capella readiness checks executable/project availability, while bridge protocol validation remains in the adapters;
- OpenProject readiness checks HTTP reachability, while API v3 optimistic locking and idempotency remain adapter responsibilities;
- object-storage readiness checks endpoint reachability, while object persistence and retention remain a later integration concern.

## Startup policy

Application startup does not block on optional external integrations. This keeps process startup deterministic and lets orchestration use `/health/ready` as the dependency gate.

Production rollout should therefore use:

1. migrate PostgreSQL;
2. start the Gateway;
3. wait for `/health/live`;
4. wait for `/health/ready` to return HTTP 200;
5. only then expose the MCP endpoint to downstream Agent/Workflow clients.

A deployment that exposes MCP while readiness is `503` is not considered operationally ready.

## Secrets

Do not put production passwords, API tokens, object-storage keys or identity credentials in the Docker image, compose file, repository, or command-line arguments. Inject them through the deployment platform's secret mechanism and map them to the typed environment variables described in `docs/deployment/production-configuration.md`.
