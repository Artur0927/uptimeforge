# MVP preparation validation — October 13, 2026

No production deployment, AWS mutation, IAM/SCP change, Terraform state edit or
billing-plan change was performed. Work was isolated from the owner's dirty
feat/aws-networking checkout. All commits retain the owner's configured identity.

| Check | Actual result |
| --- | --- |
| Application Ruff | Passed |
| Host application tests with temporary local PostgreSQL | 72 passed |
| Final pinned linux/amd64 image build | Passed |
| Final image tests with temporary PostgreSQL | 72 passed |
| Non-root, read-only API startup and database /health | Passed |
| Worker startup from the same image | Passed |
| Production Compose render/contract | Passed with synthetic configuration |
| Unsafe Compose variants | Five rejected: public DB, public API binding, mutable image, new volume, writable Worker |
| Nginx template syntax | Passed in a disposable container using a temporary test certificate |
| CI YAML parse and workflow permission review | Passed; actions pinned to verified release commits |
| Terraform readiness formatting/validation | Passed in its separate worktree |
| Terraform offline plan-only tests | Seven passed |
| OIDC diagnostic synthetic tests | Nine groups passed |

The first host pytest invocation ran from the repository root and did not load
the app's asyncio configuration. Correct invocation from app/ passed; the final
container suite also passed. No application code fix was required.

Local PostgreSQL tests used tmpfs, a random localhost port or an isolated Docker
network, and a dedicated uptimeforge_test database. Containers and networks
created by these tests were stopped/removed. No host database volume was used.
The runtime validation image remains local for inspection; it was not published.

Docker image runtime constraints were captured from the successful amd64 build;
the Python base digest and build backend are pinned. CI installs with the same
runtime constraints. Dev tool ranges and GitHub runner images remain updateable;
this is repeatable runtime resolution, not a claim of byte-identical builds.

actionlint/yamllint were unavailable locally; no result from either is claimed.
GitHub-hosted CI results must be checked after push. Live OIDC claims, provider
ownership, EC2 ECR pull authorization, private Nginx connectivity, DNS/TLS and
production backup restoration were not verified by local tests.

Before deployment, approve and review those gates in OPERATIONS.md. Keep
enable_cicd_iam=false until the separately reviewed IAM stage is authorized.
