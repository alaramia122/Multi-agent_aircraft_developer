# Staging deployment

This deployment slice runs the Engineering Gateway and its PostgreSQL state
database on one Docker host. It is intentionally private by default:

- PostgreSQL has no host port;
- Gateway is bound to `127.0.0.1:8000` only;
- the MCP actor is an AI identity with `L0_READ` authorization;
- access is provided through an SSH tunnel until a domain, TLS termination and
  production identity provider are configured.

## Prerequisites

- Docker Engine with the Compose plugin;
- the repository checked out on the target host;
- at least 8 GiB RAM and swap for the wider staging stack.

## Configure

From the repository root:

```bash
cp deployment/staging.env.example .env
password="$(openssl rand -hex 32)"
sed -i "s/REPLACE_WITH_RANDOM_HEX_PASSWORD/$password/" .env
unset password
chmod 600 .env
```

The generated password is hexadecimal so it is safe inside the PostgreSQL URL
assembled by Compose. Do not commit `.env`.

## Start

Validate the resolved Compose model before starting it:

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

The one-shot `migrate` service applies each SQL migration once and records it in
`gateway_schema_migrations`. A failed migration is rolled back and is not marked
as applied.

Verify the process from the VM:

```bash
curl --fail http://127.0.0.1:8000/health
docker compose logs --tail=100 gateway migrate postgres
```

## Access through SSH

On the operator workstation, keep this command running:

```powershell
ssh -i "$env:USERPROFILE\.ssh\engineering_staging" `
    -L 8000:127.0.0.1:8000 `
    staging@51.250.6.236
```

The local health endpoint is then available at `http://127.0.0.1:8000/health`
and Streamable HTTP MCP at `http://127.0.0.1:8000/mcp`.

## Operations

```bash
docker compose ps
docker compose logs --tail=200 gateway
docker compose restart gateway
docker compose down
```

`docker compose down` preserves the named PostgreSQL volume. Do not add `-v`
unless permanent deletion of staging data is explicitly intended.

## Deferred production controls

Before exposing MCP publicly, add all of the following:

1. a stable DNS name;
2. TLS termination with a trusted certificate;
3. an identity provider and trusted principal-to-Actor mapping;
4. separate least-privilege identities for L0/L1/L2 operations;
5. backup, monitoring and secret-management integration.

L3 approval remains human-only and must not be exposed through MCP.
