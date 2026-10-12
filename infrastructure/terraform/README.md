# UptimeForge Terraform

This live, single-AZ stack uses AWS account `152680102458`, region `eu-north-1`
and CLI profile `uptimeforge`. The existing 30 managed resource addresses are
preserved. Authentication remains IAM User → AssumeRole → UptimeForgeTerraformRole.

## Current deployment status

ECR is already deployed. Local state contains 32 managed resources: the original
30 plus the repository and lifecycle policy. The two-create example below describes
the initial ECR rollout; a current readiness plan should preserve both existing ECR
resources. The recorded validation results are historical, not a refreshed live
plan. Keep IAM disabled and inspect every future plan for unrelated drift.

## Deployment stages

The default configuration deploys **ECR only**:

```hcl
enable_cicd_iam = false
```

`module.ecr` is unconditional. `module.iam` has `count = 0` when disabled, so none
of its resources or OIDC data sources are evaluated. ECR has no dependency on
CI roles, Docker Host roles, EC2 profile changes or AWS Organizations operations.
IAM outputs return `null` and are omitted from state outputs while disabled.

Setting `enable_cicd_iam=true` later instantiates `module.iam[0]`; it does not
change ECR addresses or associate the prepared Docker Host profile with EC2.
The Docker Host continues to use the original shared SSM profile in both stages.
Attaching a new profile requires a separate reviewed compute change.

## Layout

```text
infrastructure/terraform/
├── .terraform.lock.hcl
├── providers.tf
├── versions.tf
├── main.tf
├── variables.tf
├── outputs.tf
├── terraform.tfvars.example
├── network.tf                 # existing VPC, routes and security groups
├── compute.tf                 # existing EC2 and NAT route, unchanged
├── iam.tf                     # original shared SSM role/profile, unchanged
├── bootstrap/
├── modules/
│   ├── ecr/{main,variables,outputs,versions}.tf
│   └── iam/{main,variables,outputs,versions}.tf
├── tests/
│   ├── modules.tftest.hcl      # ECR and IAM security contracts
│   └── stages.tftest.hcl       # root composition and preserved EC2 profile
├── README.md
└── README-RU.md               # existing local notes, left untouched
```

Modules inherit the root provider. AWS remains pinned to the existing lock file
(`6.68.0`, constraint `~> 6.0`). Configuration requires Terraform >= 1.5; tests
require >= 1.7. New resources receive Project, Environment and ManagedBy tags.
No provider default tags are added to existing resources. `environment=dev`
matches existing infrastructure naming; the later GitHub role authorizes `main`.

## Independent ECR infrastructure

Private repository `uptimeforge-api` uses immutable image tags, scanning on push,
AES256 encryption, `force_delete=false` and `prevent_destroy=true`. The lifecycle
policy retains the most recent 20 images with `sha-` tags by push time, and
expires untagged artifacts after seven days. Publish releases as
`sha-<40-character-git-commit-sha>`; bare SHA tags do not match release retention.
Other tagged images are outside this policy.

API and Worker will use the same versioned application image with their existing
different commands. PostgreSQL remains the official `postgres:16-alpine` image
with its `pgdata` volume and no public port. CI, Dockerfile and Compose are
unchanged in this task.

Outputs are `ecr_repository_url`, `ecr_repository_name`, `ecr_repository_arn` and
`aws_region`. They become available in state after a separately approved apply.
Lifecycle expiration can remove an image still used by a host; keep deployed and
rollback releases within the retention window before relying on future pulls.
Account-level ECR scanning settings can supersede basic repository scanning;
this stack does not change registry settings for other repositories.

## Phase 1: ECR review

From `infrastructure/terraform`:

```bash
# Optional: copy only if you do not already have private variables.
cp terraform.tfvars.example terraform.tfvars
# Keep enable_cicd_iam = false.
terraform fmt -recursive -check
terraform init -input=false -lockfile=readonly
terraform validate
terraform test
terraform plan -input=false -out=review.tfplan
terraform show review.tfplan
```

Review exactly two new resources:

```text
module.ecr.aws_ecr_repository.application
module.ecr.aws_ecr_lifecycle_policy.application
Plan: 2 to add, 0 to change, 0 to destroy.
```

Do not apply a plan with unexpected EC2, AMI, profile, network or SSM changes.
The current AMI uses a moving SSM latest parameter; inspect future plans for
unrelated AMI replacement. No apply, destroy, import or AWS write is authorized
by this task. ECR can be reviewed without resolving the OIDC SCP restriction.

## Phase 2: prepare CI/CD IAM

The IAM module implementation is retained. It prepares a GitHub ECR publisher
role, repository-scoped push policy, dedicated Docker Host role/profile, SSM
policy attachment and repository-scoped ECR pull policy. Neither the Nginx nor
NAT role receives ECR permissions. Only GetAuthorizationToken uses resource `*`;
image operations are scoped to the application repository.

1. Obtain organization-approved OIDC inspection access. The account SCP
   `p-po1vubeu` denies ListOpenIDConnectProviders and GetOpenIDConnectProvider.
   Respect it: AdministratorAccess cannot override that deny. No static AWS keys
   or provider-creation flag should be used as a workaround.
2. After access is approved, inspect the account-wide GitHub provider and choose
   reuse, confirmed-absent creation, or adoption into this state. Reuse is the
   default (`create_github_oidc_provider=false`); its audience list must include
   `sts.amazonaws.com`. Do not duplicate a provider or adopt one owned by another
   stack. If adopting, preserve its existing audiences/tags in module configuration.
3. Reverify the GitHub repository's OIDC settings:

   ```bash
   gh api repos/Artur0927/uptimeforge/actions/oidc/customization/sub
   ```

   The API was checked on October 12, 2026 and returned `use_default=true`,
   `use_immutable_subject=true`, with prefix
   `repo:Artur0927@99685228/uptimeforge@1412546510`. The retained trust uses exact
   StringEquals conditions for audience `sts.amazonaws.com` and subject:

   ```text
   repo:Artur0927@99685228/uptimeforge@1412546510:ref:refs/heads/main
   ```

   See the [GitHub OIDC reference](https://docs.github.com/en/actions/reference/security/oidc).
   Future publisher jobs must run on main, request `id-token: write`, and use the
   STS audience. Adding `environment:` changes the subject context and requires
   a separately reviewed trust contract and deployment branch protections.
4. Set `enable_cicd_iam=true` in private `terraform.tfvars`. Keep provider creation
   false for reuse; set it true only for approved creation/adoption. If an existing
   provider is being adopted, the future import address is:

   ```bash
   terraform import 'module.iam[0].aws_iam_openid_connect_provider.github[0]' \
     'arn:aws:iam::152680102458:oidc-provider/token.actions.githubusercontent.com'
   ```

   This is a future ownership step, **not executed in this task**. Once managed,
   keep the creation flag true; changing it would propose provider destruction,
   which prevent_destroy blocks.
5. Run fmt, init, validate, test and a fresh plan. After ECR is deployed, expect
   six IAM creates for reuse, or seven including a new provider; adopting one
   accounts for it through import. Require zero EC2 changes, replacements or
   destructions. Review authorization to create roles/policies and attach SSM.
   IAM/ECR creation permissions are not proven merely by a successful plan.

The current state contains no IAM module resources, so introducing module count
requires no moved blocks or state imports. ECR remains `module.ecr` in both
stages. Once IAM is deployed, disabling its flag would propose deletion of its
resources; keep it enabled unless a separate teardown is explicitly reviewed.

## Later Docker Host and SSM deployment integration

After the IAM stage is approved and deployed, separately change only the Docker
Host's `iam_instance_profile` to
`module.iam[0].docker_host_instance_profile_name`. Review a plan for one in-place
EC2 profile association update and zero replacements. The prepared profile
already depends on its SSM attachment and ECR pull policy. The Terraform role
will need PassRole for this role and EC2 association permissions. Allow for IAM
propagation and verify a fresh SSM session and host identity after migration.
The shared SSM role/profile remains for Nginx and NAT.

A subsequent workflow can test, build `app/` once, authenticate with OIDC, and
publish `sha-${GITHUB_SHA}`. Handle retries of already-published immutable tags.
Automatic deployment through SSM needs a separately reviewed deploy policy
scoped to approved command documents and the Docker Host, command-status polling,
release validation, concurrency control and rollback handling. The current
publisher role has ECR permissions only and cannot send SSM commands.

Deployment must pull the same SHA image for API and Worker, run migrations
explicitly, and preserve the PostgreSQL volume. The current API Compose binding
is loopback; a later production configuration must address private Nginx-to-API
connectivity and TLS without publicly exposing PostgreSQL or opening SSH.
No production workflow or deployment policy is implemented here.

## Validation results

The ECR-only checks on October 12, 2026 used Terraform 1.16.1 and AWS 6.68.0:

| Check | Result |
| --- | --- |
| terraform fmt -recursive / formatting check | Passed |
| terraform init -input=false -lockfile=readonly | Passed; lock file unchanged |
| terraform validate | Passed |
| terraform test | Six plan-only tests passed; no AWS writes |
| Default live terraform plan -input=false | 2 create, 0 change, 0 replace, 0 destroy |
| Original 30 managed resources | All no-op, with original state addresses |

The default plan has no IAM module instance or OIDC lookup. Only repository and
lifecycle policy creation are proposed. No apply, destroy, import or AWS write
was run. State and lock file checksums remain unchanged.

`.gitignore` excludes state, .terraform/, private .tfvars, saved .tfplan files and
secrets. Keep non-secret terraform.tfvars.example and the lock file in Git; keep
plan JSON/logs outside the repository. Existing uncommitted work is preserved.

## Cross-platform provider verification

GitHub's Linux runner requires its own verified provider package hash. The lock
file now records linux_amd64 alongside the existing macOS hash, fetched from the
official registry and signed by HashiCorp. AWS stays at 6.68.0; this is not a
provider upgrade or state migration. Regenerate/review platform hashes with
`terraform providers lock -platform=darwin_arm64 -platform=linux_amd64` when
maintaining the pinned provider. CI continues to use lockfile=readonly.
