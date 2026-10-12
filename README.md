# UptimeForge

A learning project with a functional website and API availability monitoring
application. The web application and monitoring worker run as separate Python
processes and share PostgreSQL. Infrastructure is owned by the DevOps learner.

## Features

- Create, list, edit and delete monitors with a name, public URL and check interval.
- Asynchronous HTTP GET checks, status codes, response times and UTC check history.
- Manual **Check now** and independent periodic monitoring worker.
- Responsive dark dashboard with real overview statistics, charts, monitor details,
  forms, empty states and actionable errors. No frontend build pipeline.
- Authenticated dashboard, API and interactive API documentation.
- SQLAlchemy 2 models, explicit sessions, Alembic migration, structured application
  logs and application tests.

## Architecture

FastAPI routes validate input and call the monitoring service. HTTPX resolves and
checks public destinations; SQLAlchemy stores the latest monitor state and every
check result in a single transaction. The dashboard uses Jinja2 with local CSS and
JavaScript, including a native canvas chart. A worker polls for due monitors and
uses PostgreSQL `FOR UPDATE SKIP LOCKED` to prevent duplicate checks across worker
processes. Each concurrent worker lane owns its own session.

The web process does **not** start a scheduler or automatically migrate the database.
Checks hold the monitor row lock for their duration. Concurrent manual checks,
updates or deletes return `409` for a busy monitor. A crash rolls back the transaction
and releases the lock; the next worker poll can retry. Graceful worker shutdown lets
in-flight checks finish within their deadline. Unexpected worker errors roll back
and are retried on a later poll.

```text
app/
├── pyproject.toml           # Runtime dependencies and test/static-check tools
├── .env.example            # Configuration placeholders, no real credentials
├── alembic.ini
├── migrations/             # Initial PostgreSQL schema and Alembic environment
├── uptimeforge/
│   ├── main.py             # FastAPI, authentication, errors and dashboard routes
│   ├── api.py              # Monitor CRUD, manual checks and history
│   ├── config.py           # Validated environment settings
│   ├── db.py               # Engine, session factory and request sessions
│   ├── models.py           # Monitor and CheckResult tables, indexes, constraints
│   ├── schemas.py          # Request/response validation and UTC serialization
│   ├── security.py         # URL policy, DNS validation and IP pinning
│   ├── monitoring.py       # Bounded HTTP checks and atomic result persistence
│   ├── worker.py           # Separate periodic monitoring process
│   ├── logging.py          # JSON application logs without target URLs or secrets
│   ├── templates/          # Dashboard and monitor details
│   └── static/             # CSS and lightweight JavaScript
└── tests/                  # Unit, API, worker, migration and optional PG tests
infrastructure/             # Existing DevOps-owned files; application work leaves them alone
```

## Local development

Use Python 3.12+ and an existing PostgreSQL database with a dedicated application
user. Database/server provisioning is intentionally outside this project task.

From the repository root:

```bash
cd app
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
```

Edit `app/.env` with your actual database URL, username and a long random password.
Example placeholders are not usable credentials; the application refuses the
example authentication password. The file is ignored by Git. Environment variables
override `.env`. Commands below assume the working directory is `app/`.

Run the database migration, then the application:

```bash
alembic upgrade head
uvicorn uptimeforge.main:app --host 127.0.0.1 --port 8000 --reload --no-access-log
```

In another terminal, activate the same virtual environment and start the worker:

```bash
cd app
source .venv/bin/activate
python -m uptimeforge.worker
```

Open `http://127.0.0.1:8000` and enter `AUTH_USERNAME` / `AUTH_PASSWORD` in the
browser's Basic authentication dialog. The web application listens on port 8000;
the worker has no inbound port. Without the worker, manual checks still work.

To inspect migration SQL without connecting or applying changes:

```bash
alembic upgrade head --sql
```

## Environment variables

| Variable | Required / default | Purpose |
|---|---|---|
| `DATABASE_URL` | Required | `postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE`; URL-encode special characters in credentials |
| `AUTH_USERNAME` | Required | Shared administrator username |
| `AUTH_PASSWORD` | Required | Administrator password, at least 12 characters; use a long random value |
| `CHECK_TIMEOUT_SECONDS` | `10` (1–60) | Total deadline covering DNS, TLS, headers and body |
| `MAX_RESPONSE_BYTES` | `1048576` | Maximum raw response body bytes (1024–10485760) |
| `WORKER_POLL_SECONDS` | `2` (0.5–60) | Delay when no monitor is due or a worker error occurs |
| `WORKER_CONCURRENCY` | `5` (1–20) | Concurrent checks per worker process |
| `UPTIMEFORGE_TEST_DATABASE_URL` | Optional, tests only | Existing migrated, empty PostgreSQL database whose name ends in `_test` |

Web and worker processes need the same application settings. Secrets must be
supplied by the operator and never committed or embedded in an image.

## API

Interactive documentation: `/docs` (Swagger), `/redoc`; schema: `/openapi.json`.
All are authenticated. Swagger exposes Basic authentication and the request header
required for write operations.

| Method | Endpoint | Behavior |
|---|---|---|
| GET | `/health` | Public database connectivity check; `200` or `503`, no secrets |
| GET | `/api/monitors` | List monitors; `limit` 1–500, default 100, and `offset` |
| POST | `/api/monitors` | Create monitor; `201` |
| GET | `/api/monitors/{id}` | Read monitor; `200` or `404` |
| PATCH | `/api/monitors/{id}` | Partial update; `200`, `404`, or `409` if busy |
| DELETE | `/api/monitors/{id}` | Delete monitor and its history; `204`, `404`, or `409` |
| POST | `/api/monitors/{id}/check` | Persist a manual check result; `200`, `404`, or `409` |
| GET | `/api/monitors/{id}/history` | Newest-first history, `limit` 1–500 and `offset` |

Create example (curl prompts for the configured password):

```bash
curl --user "$AUTH_USERNAME" \
  -H 'Content-Type: application/json' \
  -H 'X-UptimeForge-Request: 1' \
  -d '{"name":"Example website","url":"https://example.com","interval_seconds":60}' \
  http://127.0.0.1:8000/api/monitors
```

If credentials are only in `.env`, enter the username in place of `$AUTH_USERNAME`.
Write operations require `X-UptimeForge-Request: 1`; this header plus the same-origin
policy protects browser Basic credentials against CSRF. Errors have the shape
`{"error":{"code":422,"message":"Validation failed","details":[...]}}`;
validation details are present only for input validation errors. HTTP check failures
are successful API operations that persist a `DOWN` result, not API server errors.

Intervals are 30–86400 seconds. `PENDING` means no check has completed for the current
target. HTTP 200–399 is `UP`; redirects are counted as reachable but never followed.
HTTP 400+, DNS failures, blocked destinations, TLS/network errors, timeouts and
oversized responses are `DOWN`. Response time includes DNS and the streamed body.
The next check is scheduled from completion, so the interval is a minimum pause,
not an exact wall-clock cadence. Changing a URL resets current status to `PENDING`
and preserves history with each result's original `target_url`.

Dashboard averages use the latest result of each checked monitor, including failed
checks. Its overview chart shows the last 50 checks across monitors; details show
the last 100 checks. History beyond that is available through the paginated API.
Dashboard lists have 50 monitors per page and search filters the current page.
Reload the dashboard to see results recorded by the worker.

## Tests and checks

```bash
cd app
source .venv/bin/activate
pytest -q
ruff check .
ruff format --check .
python -m pip check
```

If Node.js is available, JavaScript syntax can also be checked without a build step:

```bash
node --check uptimeforge/static/app.js
```

The default suite uses in-memory SQLite for repository/API behavior, mocked outbound
HTTP and DNS, and a real HTTPX/HTTPCore transport with a fake socket to verify IP
pinning, TLS hostname verification configuration and the original Host header.
It also generates PostgreSQL migration SQL offline. It needs no cloud or network.
SQLite does **not** validate PostgreSQL row locking, timestamps or live migrations.

Two opt-in PostgreSQL tests verify busy-monitor conflicts and concurrent worker
locking. A DevOps engineer must first supply a separate empty `*_test` database
and apply the application's migration there. Then:

```bash
UPTIMEFORGE_TEST_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@HOST/uptimeforge_test' \
  pytest -q tests/test_postgres.py
```

The fixture refuses a non-test database name or a non-empty monitors table, creates
only its own application records and removes those records afterward. It does not
install a server, create a database or migrate an existing database. Never point
tests at production. PostgreSQL tests are explicitly skipped when the test URL is
absent; a skip is not a successful PostgreSQL integration test.

## Security and MVP limits

URLs are untrusted. Only HTTP/HTTPS on ports 80 and 443 are allowed. Credentials,
fragments, local hostnames, private/reserved/metadata IPs, scoped IPv6 and IPv6
translation/tunnel addresses are rejected. Creation and URL updates validate all
DNS answers; each actual check resolves and validates again, then connects to a
specific validated numeric address. The original hostname is used for HTTP Host,
TLS SNI and certificate verification, closing the resolve-then-rebind gap. Automatic
redirects and environment proxies are disabled. Response bodies are streamed raw,
bounded and discarded, with no decompression; response contents and target URLs
are not included in application logs.

Remaining limits:

- One shared administrator; no tenant isolation, RBAC, sessions or password-reset
  flow. Basic authentication requires HTTPS outside local development; browsers
  may cache credentials. Keep access restricted and configure authentication rate
  limits before public exposure.
- SSRF protection assumes normal network routing. Public-address routing overrides,
  custom NAT/NAT64 prefixes or proxies outside the process need network-level egress
  controls. Only the first validated DNS address is attempted; there is no failover.
- DNS lookups use the operating system resolver. The check deadline bounds the
  application wait, but an underlying resolver thread may finish later.
- No history retention, alert delivery, quotas, distributed rate limiting or uptime
  percentage calculation. Operators must plan database growth and access limits.
- Full response transfer contributes to response time. Sites over the configured
  size limit are marked DOWN; adjust the setting or monitor a smaller health URL.
- Dashboard data updates on page reload. API docs use FastAPI's default external
  Swagger/ReDoc assets; the dashboard uses only bundled assets.

## Container operations

Reviewed production Compose, migration, backup, rollback and Nginx procedures are
in [docs/OPERATIONS.md](docs/OPERATIONS.md). Deployment assets are prepared; AWS
OIDC, Docker Host ECR pull access and production activation remain approval gates.

## DevOps handoff

AWS infrastructure and ECR/IAM review instructions are in
[`infrastructure/terraform/README.md`](infrastructure/terraform/README.md).

The DevOps engineer owns PostgreSQL provisioning/users, secret injection, database
backups, TLS and restricted ingress, egress controls, process supervision and running
the web and worker separately. They must run migrations explicitly before startup
and arrange logs, retention and operational health checks. Containerization, AWS,
Terraform, Nginx, CI/CD, deployment and monitoring configuration are deliberately
outside application development. No application changes are needed in the existing
`infrastructure/` directory.
