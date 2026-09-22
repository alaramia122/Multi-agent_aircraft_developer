# Yandex Cloud single-VM staging

This profile deploys the selected external staging boundary on one Yandex Cloud
VM. It uses maintained components and keeps the Gateway governance model
unchanged:

- Caddy for TLS termination and public routing;
- Keycloak as the staging OIDC provider;
- OAuth2 Proxy for OIDC token/session verification;
- Engineering Gateway and ordered SQL migrations;
- PostgreSQL for Gateway state plus separate Keycloak and OpenProject databases;
- OpenProject Community Edition and Memcached;
- the official StrictDoc CLI inside the Gateway image;
- a mounted Capella bridge executable and project supplied by the deployment.

The Gateway container has no published port. Caddy is the only public ingress,
and the PostgreSQL network is internal. OAuth2 Proxy verifies the external
principal. Caddy overwrites the internal Actor headers and adds a shared hop
secret; the Gateway converts only that authenticated internal hop to ASGI trusted
principal state. A public client cannot set those claims directly.

## Capacity and network

Use Ubuntu 24.04 LTS with at least 4 vCPU, 12 GB RAM and an 80 GB network SSD.
Use 16 GB RAM when the Capella headless runtime runs on the same VM. In the
Yandex Cloud security group allow:

- TCP 22 only from the administrator CIDR;
- TCP 80 and TCP/UDP 443 from intended staging clients;
- no public rules for 5432, 8000, 8080, 4180, 11211 or Capella bridge ports.

Create three DNS A records pointing to the VM public address: Gateway, IdP and
OpenProject. The exact names are supplied in `.env`.

## Host bootstrap

Install Docker Engine and the Docker Compose plugin from Docker's supported
Ubuntu repository, then clone this repository on the VM. From the repository
root:

```bash
mkdir -p deploy/yandex-vm/data/strictdoc
mkdir -p deploy/yandex-vm/data/strictdoc-bridge
mkdir -p deploy/yandex-vm/data/capella
mkdir -p deploy/yandex-vm/data/capella-bridge
cp deploy/yandex-vm/.env.example deploy/yandex-vm/.env
chmod 600 deploy/yandex-vm/.env
```

Fill `.env` with the real DNS names and unique secrets. Useful generators are:

```bash
openssl rand -hex 32
openssl rand -base64 32
openssl rand -hex 64
```

`OAUTH2_PROXY_COOKIE_SECRET` must be a valid OAuth2 Proxy cookie secret. Use the
32-byte Base64 value. Pin `STRICTDOC_PACKAGE` to an exact version after the first
qualified build; the unpinned value is only a bootstrap default.

Validate interpolation before starting containers:

```bash
docker compose \
  --env-file deploy/yandex-vm/.env \
  -f deploy/yandex-vm/compose.yml \
  config --quiet
```

## Bootstrap order

1. Start PostgreSQL, Keycloak and OpenProject:

   ```bash
   docker compose --env-file deploy/yandex-vm/.env \
     -f deploy/yandex-vm/compose.yml \
     up -d postgres keycloak memcached openproject caddy
   ```

2. Sign in to `https://IDP_DOMAIN/admin/`. The imported realm is
   `engineering-staging`. In that realm create a confidential OIDC client whose
   client ID matches `OAUTH2_PROXY_CLIENT_ID`, with this exact redirect URI:

   ```text
   https://GATEWAY_DOMAIN/oauth2/callback
   ```

   Add an audience mapper so access tokens include that client ID in `aud`, then
   put the generated client secret in `OAUTH2_PROXY_CLIENT_SECRET`. Create only
   the staging users/service accounts that are required. The MCP ingress maps
   all accepted principals to an AI actor capped at L2. It never grants L3
   approval.

3. Complete the OpenProject first-run setup at
   `https://OPENPROJECT_DOMAIN/`. Create the staging project, a `Change Request`
   work-package type, and a dedicated API user. Put the API token and numeric IDs
   into `.env`; then set `OPENPROJECT_ENABLED=true`.

4. Place the authoritative `.sdoc` project in `STRICTDOC_PROJECT_DIR`. Build and
   test the pinned StrictDoc image, then set `STRICTDOC_ENABLED=true`. Read access
   uses the official CLI. For governed publication, place an executable named
   `strictdoc-bridge` under `STRICTDOC_BRIDGE_DIR`; it must implement
   `docs/contracts/strictdoc-adapter.md`. Only then set
   `STRICTDOC_WORKSPACE_MUTATIONS_ENABLED=true`.

5. Place the Capella model under `CAPELLA_PROJECT_DIR` as `project.aird`. Place
   an executable named `capella-bridge` under `CAPELLA_BRIDGE_DIR`. It must
   implement the versioned JSON bridge contract in
   `docs/contracts/capella-adapter.md`. Set `CAPELLA_ENABLED=true` only after a
   direct bridge contract test succeeds.

6. Start or recreate the complete stack:

   ```bash
   docker compose --env-file deploy/yandex-vm/.env \
     -f deploy/yandex-vm/compose.yml \
     up -d --build
   ```

## Verification

Inspect container state and the non-sensitive public liveness endpoint:

```bash
docker compose --env-file deploy/yandex-vm/.env \
  -f deploy/yandex-vm/compose.yml ps
curl --fail "https://$GATEWAY_DOMAIN/health/live"
```

Readiness is intentionally not exposed through Caddy because it contains
dependency details. Run it on the VM:

```bash
docker compose --env-file deploy/yandex-vm/.env \
  -f deploy/yandex-vm/compose.yml \
  exec gateway python -c \
  "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health/ready').read().decode())"
```

Every enabled integration must report `ready`. A disabled integration is not
evidence of external E2E completion.

Verify both identity paths:

- an unauthenticated request to `/mcp` is rejected by OAuth2 Proxy;
- a valid bearer token issued by the staging realm reaches Gateway with the
  verified upstream user identity as `Actor.actor_id` and the AI/L2 cap;
- direct access to port 8000 is impossible from outside the Docker network;
- missing, duplicate or invalid internal proxy headers fail closed.

Then execute the MVP-1 and MVP-2 scenarios from `docs/deployment/staging-e2e.md`.

## Backups and updates

Before an image or schema update, stop mutations and back up the PostgreSQL
volume plus OpenProject assets and authoritative StrictDoc/Capella/Git data.
Do not treat a VM disk snapshot alone as a verified database backup. Restore to
a disposable VM and rerun readiness and E2E before relying on the backup.

Never commit `.env`, database dumps, API tokens, Capella models or generated
evidence. Rotate the Caddy/Gateway shared secret and OAuth client secret together
through a controlled restart.

## Honest deployment boundary

This directory makes the VM topology reproducible, but it does not manufacture
the deployment-specific Capella bridge, DNS records, credentials, OpenProject
workflow or Yandex AI Studio connection. The external staging phase is complete
only after those real resources pass the governed E2E gate.
