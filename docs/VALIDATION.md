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

Remote validation before the documentation handoff:

- [Production application CI](https://github.com/Artur0927/uptimeforge/actions/runs/38310633090) passed.
- [Terraform CI](https://github.com/Artur0927/uptimeforge/actions/runs/38310855686) passed after
  adding the HashiCorp-signed Linux package hash, retaining AWS provider 6.68.0.
- Initial draft PRs targeted feat/aws-networking. The owner subsequently merged
  networking/ECR (#3) and the Terraform refactor (#4). Integration review merges
  current main into each feature branch without rewriting history and retargets
  #5/#6/#7 to main. No PR was merged during this integration review.

## Final integration review

- Main 52338dd already contains networking/ECR via #3 and the Terraform root
  refactor 1c6201e via #4. Each feature branch merged main without rebasing or
  force-pushing; existing history and the dirty owner checkout were preserved.
- Repeated validation: Ruff, 72 image tests against disposable PostgreSQL,
  non-root/read-only API database health, Worker startup, seven offline Terraform
  plan tests, nine synthetic OIDC groups, Compose contract and five rejected
  unsafe variants all passed. Operations Bash examples passed syntax checks only.
- A second disposable PostgreSQL 16 restored a custom-format dump from a freshly
  initialized/migrated database; Alembic 0001 and a synthetic monitor survived.
  Both databases used tmpfs; no persistent volumes were created or removed.
- Compose and CI YAML parse. Quoting no-new-privileges:true also makes the Compose
  file compatible with the local older Ruby YAML parser. The first Terraform
  provider invocation was blocked by sandbox plugin-socket restrictions; rerunning
  the same offline checks with local socket access passed. No AWS API was called.
- Fresh initialization now requires explicit volume-creation/migration approval;
  upgrades select the actual existing volume and migrations use --no-deps.
- Manual publication requires an approved temporary human/SSO session. The existing
  AssumeRole profile is not evidence that its source avoids static IAM-user keys.
- Release remains blocked on host-only IAM/profile approval independent of OIDC,
  approved temporary publisher access, host/private proxy/TLS verification,
  production backup restore evidence and actual AWS billing-plan confirmation.
  Organizations membership conflicts with a strict Free account plan requirement
  under current AWS documentation; no billing/organization change was made.
