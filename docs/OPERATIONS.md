# UptimeForge MVP operations

This is a single-AZ deployment, not a highly available service. The repository
prepares deployment assets; none of these instructions authorizes a production
change. Obtain explicit approval before deploying, migrating data, modifying
Nginx, associating IAM profiles or changing AWS resources. Preserve the AWS Free
Plan; no paid services or billing changes are required by these assets.

## Architecture and boundaries

```mermaid
flowchart LR
    Browser -->|HTTPS 443| Nginx[Public Nginx EC2]
    Nginx -->|Private TCP 8000| API[Docker Host API: 10.20.2.23]
    Worker[Docker Host Worker] --> DB[(PostgreSQL 16 volume)]
    API --> DB
    API -->|HTTP/HTTPS monitoring| NAT[Linux NAT EC2]
    Worker -->|HTTP/HTTPS monitoring| NAT
    NAT --> Internet
    SSM[Session Manager] -->|Outbound agent connection| Hosts[All EC2 hosts]
```

The VPC is 10.20.0.0/16; private services are in 10.20.2.0/24. The existing SG
allows API ingress only from Nginx's SG. Production Compose binds API port 8000
only to the Docker Host's private IP. PostgreSQL has no host port; Worker has no
listener. SSH is not needed. ECR/SSM access depends on outbound HTTPS via the
working NAT and routes. Do not recreate networking to deploy the application.

Use the existing local profile to request an approved SSM session:

```bash
aws sts get-caller-identity --profile uptimeforge --region eu-north-1
# Use the existing Docker Host instance ID from the reviewed Terraform output:
aws ssm start-session --target INSTANCE_ID --profile uptimeforge --region eu-north-1
```

The local workstation's AWS credentials are not container configuration. Do not
copy them to GitHub, EC2 files or .env.prod. Do not run Docker remotely through an
unprotected TCP socket.

## Current readiness gates

- ECR uptimeforge-api is deployed; `enable_cicd_iam=false` remains unchanged.
- Real GitHub OIDC claim diagnostics must be reviewed after their workflow is
  merged into main. Organization-approved provider inspection is still blocked
  by SCP p-po1vubeu; do not create a provider to bypass that restriction.
- The Docker Host still uses the shared SSM role. A separately approved dedicated
  profile migration is required before instance credentials can pull ECR images.
  Enabling the prepared IAM module alone does not associate a profile.
- Publishing and deployment workflows are not active. No permanent AWS keys
  are used as a workaround. An approved operator with repository-scoped push
  access can publish the linux/amd64 image; never assume the Terraform operator
  profile is authorized to publish before checking its approved permissions.
- DNS, certificates and Nginx reverse proxy activation remain operator decisions.
  Do not send Basic authentication credentials over public HTTP.

## Images and configuration

The Dockerfile pins the Python base digest, build backend and runtime constraints
in app/requirements.lock. CI uses those runtime constraints too. Dependency/base
updates require a reviewed lock/digest change and the complete test suite.

Build from app/ for linux/amd64 (the current EC2 hosts are x86_64). Every release
uses the same image for API and Worker:

```text
152680102458.dkr.ecr.eu-north-1.amazonaws.com/uptimeforge-api:sha-FULL_40_HEX_COMMIT_SHA
```

Tags are immutable. An already-published SHA should be verified and reused, not
overwritten. Keep running/rollback releases within ECR's 20-image retention
window. Record the resolved image digest as well as the Git commit. PostgreSQL
stays on official postgres:16-alpine; review minor updates separately.

Copy .env.prod.example to a protected .env.prod, replace every placeholder, and
set permissions to 600. Docker administrators can inspect container environment
values; restrict Docker and SSM access. Never print resolved Compose configuration
with real secrets in shared logs; use `config --quiet` for routine validation.

POSTGRES_VOLUME_NAME must be the **actual existing volume**, not a guessed new
name. Inspect the current database container's mounts before approval. The
external volume declaration refuses to silently provision an empty database.
POSTGRES_DB, POSTGRES_USER and POSTGRES_PASSWORD must match the existing database;
changing those image initialization variables does not rotate existing database
credentials. URL-encode credentials in DATABASE_URL and use hostname db.

The API needs a long random AUTH_PASSWORD; example REPLACE_ values are rejected.
Keep backups and release records outside the 20 GiB host disk where practical.
No secret file is committed or bundled into the application image.

## Approved manual deployment procedure

Run host commands from a private, operator-owned checkout/release directory on
the Docker Host. Verify local Docker context and the target host before changes.
Use an approved credential mechanism after the ECR pull role is associated:

```bash
aws sts get-caller-identity --region eu-north-1
aws ecr get-login-password --region eu-north-1 | docker login \
  --username AWS --password-stdin 152680102458.dkr.ecr.eu-north-1.amazonaws.com
```

This uses temporary instance-role credentials, not the workstation profile.
Protect Docker's credential storage or configure the ECR credential helper;
refresh login when its token expires. Do not print the password.

After explicit deployment approval:

1. Verify free disk/RAM, the existing volume name, database health and a restorable
   backup. Record the previous SHA, digest, Compose revision and Alembic revision.
2. Set the new APP_IMAGE in the private configuration. Run
   `docker compose --env-file .env.prod -f compose.prod.yaml --profile tools config --quiet`.
3. Pull without stopping running containers:
   `docker compose --env-file .env.prod -f compose.prod.yaml pull api worker migrate`.
4. For initial adoption, review container names, project labels and database
   settings against the running Compose stack before any recreation. This file
   uses project name uptimeforge. Do not run two database containers on one volume.
5. Stop only API and Worker during a schema upgrade:
   `docker compose --env-file .env.prod -f compose.prod.yaml stop api worker`.
6. After migration-specific approval, invoke the one-off migration explicitly:
   `docker compose --env-file .env.prod -f compose.prod.yaml --profile tools run --rm migrate`.
   Its exit code must be zero before startup. No migrations run implicitly in API.
7. Start the app services:
   `docker compose --env-file .env.prod -f compose.prod.yaml up -d --no-deps api worker`.
   The existing database must already be healthy. Monitor `ps`, API /health,
   worker logs and a real monitor's check history. Health failures do not cause
   Docker to restart a running-but-unhealthy container automatically.
8. Verify Nginx-to-private-IP connectivity and HTTPS access before declaring the
   release usable. Run `docker logout` if temporary login storage should be cleared.

Never use down -v, volume rm, system prune --volumes, or recreate the database
volume during an update. A migration failure requires investigation and a reviewed
recovery decision; do not automatically downgrade the schema or restore backups.

## Rollback, backup and recovery

For an application-only rollback with a compatible schema, restore the recorded
previous APP_IMAGE, pull it, and recreate only API/Worker. Verify health and check
history. If the migration is incompatible, stopping services and restoring data
requires separate approval; a previous image alone is not a database rollback.
Initial migration 0001 creates the current schema; future migrations must state
compatibility and rollback constraints before release.

An approved backup can use a PostgreSQL custom-format dump without exposing
the database port or printing its password:

```bash
umask 077
docker compose --env-file .env.prod -f compose.prod.yaml exec -T db \
  sh -c 'exec pg_dump --format=custom --username="$POSTGRES_USER" "$POSTGRES_DB"' \
  > /SECURE_BACKUP_LOCATION/uptimeforge.dump
```

Check command success and use pg_restore --list to inspect the archive. Test
restoration into an isolated PostgreSQL 16 database and verify migrations, monitor
counts and API behavior. Encrypt and copy backups off-host through an approved
storage process. Define retention, recovery point/time objectives and a schedule;
none is automated here. Do not test restores against production or copy a live
PostgreSQL data directory as a substitute for a consistent backup.

## Proxy, health and security

deploy/nginx/uptimeforge.conf.example is a template, not an applied configuration.
Replace the domain and certificate paths; verify DNS and private connectivity;
validate with nginx -t before an approved reload. Its access format omits query
strings and authorization headers. Configure log rotation and Basic-auth rate
limiting before public use. The existing bootstrap currently serves a test page.

API /health performs a database query. Worker health checks database access;
they do not prove scheduling progress. Alert on stalled check history, worker
errors, database/disk growth, unhealthy containers and NAT/SSM availability.
Logs rotate at 10 MiB × three files per container. Start memory limits are DB
512 MiB, API 384 MiB and Worker 256 MiB, leaving headroom on t3.small. CPU limits
are 0.5 per service; validate burst-credit use and memory under realistic load.
Check history is not yet pruned automatically; 20 GiB EBS needs growth monitoring.

The application rejects private/metadata addresses, dangerous URL forms and DNS
answers; each check pins a validated public IP while preserving TLS hostname
verification. Body size, redirects and deadlines are constrained. Unit tests cover
these SSRF protections. Network routing overrides remain an operator risk; review
them before allowing arbitrary public checks. Do not relax these controls to reach
internal services. Keep one authenticated administrator, restrict access and avoid
describing this single-tenant MVP as a multi-tenant production SaaS.

## Troubleshooting

- ECR AccessDenied: verify the host's actual role and repository-scoped pull policy;
  keep the SCP intact and do not install static credentials.
- SSM offline or pull timeouts: inspect the existing NAT route, HTTPS egress, agent
  health and IAM association. Do not open SSH as a workaround.
- API unhealthy: inspect sanitized app logs, db health, credentials and migration
  revision; no auto-migration occurs during web startup.
- Worker healthy but checks stall: inspect worker logs, due monitors, database locks
  and actual check timestamps. The DB health probe does not detect a stuck scheduler.
- Missing external volume: stop and identify the existing mount; do not create an
  empty replacement volume to satisfy Compose.
- Disk pressure: inspect log and check-history growth; prune only reviewed unused
  images without volumes, and preserve rollback candidates and data backups.
