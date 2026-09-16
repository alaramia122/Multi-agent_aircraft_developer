# Production Configuration

## Purpose

The Gateway uses one typed runtime configuration model for the process itself, the database, MCP, identity boundary and external engineering integrations. Configuration is deployment input; it does not become part of the engineering source of truth.

Implementation: `src/engineering_gateway/config.py`.

## Environment convention

`pydantic-settings` loads environment variables with `__` as the nested delimiter:

```text
GATEWAY__PORT=8000
DATABASE__URL=postgresql+psycopg://...
MCP__PATH=/mcp
OPENPROJECT__API_TOKEN=...
```

See `.env.example` for the complete variable set. Real `.env` files and deployment secrets must never be committed.

## Configuration groups

| Group | Responsibility | Production notes |
| --- | --- | --- |
| `gateway` | HTTP listener, environment, version, log level | Environment is explicit: `development`, `staging`, `production`, or `test`. |
| `database` | PostgreSQL URL and pool policy | PostgreSQL remains Gateway state storage, not an engineering-model mirror. |
| `identity` | External identity-provider boundary | Disabled by default; principal-to-Actor mapping remains a deployment concern. |
| `mcp` | Streamable HTTP path, host/origin allowlists, temporary static Actor | Static actor defaults to L0 READ and is not a production identity substitute. |
| `git` | Local Git adapter | Repository root and subprocess timeout are explicit. |
| `strictdoc` | StrictDoc CLI | Disabled until an actual project path is supplied. |
| `capella` | Headless Capella bridge | Disabled until executable and project path are supplied. |
| `openproject` | OpenProject API v3 | Disabled until URL, token and work-package IDs are supplied. |
| `object_storage` | S3-compatible artifact storage | Disabled until endpoint, bucket and credentials are supplied. |

## Validation rules

The configuration layer fails fast for invalid deployment input:

- ports are within the TCP port range;
- timeouts are positive;
- required enabled integrations have their mandatory fields;
- MCP path is absolute and static Actor ID is non-blank;
- database URL is non-blank;
- OpenProject and Object Storage credentials use `SecretStr`;
- disabled optional integrations do not require deployment-specific values.

The integration adapters retain their own protocol-specific validation. Configuration validation therefore checks deployment completeness without duplicating adapter semantics.

## Secret handling

Secrets are typed as `SecretStr` where the configuration owns credentials. Pydantic serialization masks these values. Secrets must still be supplied through the deployment secret mechanism rather than Git, source code, or command-line arguments where the platform can expose them.

The configuration model does not log or print secret values.

## Static Actor boundary

The current static MCP actor exists for local/development composition and preserves the Gateway authorization contract. Its default authorization level is `L0_READ`. Production deployments must introduce the external identity provider and trusted principal-to-Actor mapper before granting a principal higher authorization.

No MCP argument, model-generated text, annotation or configuration value supplied by an untrusted caller is an authorization grant.

## Startup policy

Configuration construction is intentionally separate from integration readiness:

1. configuration validates syntactic and deployment-completeness constraints;
2. application startup constructs process resources from the validated configuration;
3. the later readiness layer checks database and enabled external integrations;
4. a disabled optional integration is reported as disabled, not silently treated as healthy.

This keeps configuration deterministic and makes missing production dependencies visible without forcing every development checkout to provision every external system.

## Non-goals

This layer does not yet:

- implement an identity provider;
- perform health/readiness probes for external systems;
- instantiate all external adapters in the composition root;
- store or retrieve Object Storage objects;
- define deployment-platform-specific secret injection.

Those concerns belong to the subsequent deployment/readiness and concrete integration stages.
