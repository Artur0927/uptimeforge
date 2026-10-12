# DEVOPS-015: GitHub OIDC diagnostics handoff

Prepared on `feat/aws-networking`. The separate
[`oidc-diagnostics.yml`](workflows/oidc-diagnostics.yml) workflow requests a GitHub
OIDC token and checks its claims without authenticating to AWS. Existing CI tests,
Ruff, PostgreSQL migrations and Docker build are unchanged.

## Run after merging into main

1. Review the workflow and merge it into the default branch `main` through the
   normal review process. No commit, push, merge or remote run was performed here.
2. Open `Artur0927/uptimeforge` on GitHub, select **Actions**, then **GitHub OIDC
   diagnostics** in the workflow list.
3. Select **Run workflow**, choose branch **main**, then **Run workflow**. The
   workflow must exist on the default branch for manual dispatch. Selecting any
   other branch skips the job; it does not verify claims.
4. Open the run, select **inspect-claims**, then expand **Inspect expected OIDC
   claims without AWS authentication**. Review every claim result.

Alternatively, after merge, a user with repository access can dispatch:

```bash
gh workflow run oidc-diagnostics.yml --repo Artur0927/uptimeforge --ref main
gh run list --repo Artur0927/uptimeforge --workflow oidc-diagnostics.yml --limit 5
# Substitute the run ID printed by the previous command:
gh run view RUN_ID --repo Artur0927/uptimeforge --log
```

These are future instructions, not commands executed during preparation. See
[GitHub's manual workflow instructions](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).

## Expected results

```text
PASS execution_context
Diagnostics only: JWT signatures are not independently validated.
PASS token_request_or_decode
PASS iss
PASS aud
PASS sub
PASS ref
PASS repository
PASS repository_owner
PASS repository_id
PASS repository_owner_id
PASS claim_checks
```

The required expected claims are:

| Claim | Expected value |
| --- | --- |
| iss | https://token.actions.githubusercontent.com |
| aud | sts.amazonaws.com |
| sub | repo:Artur0927@99685228/uptimeforge@1412546510:ref:refs/heads/main |
| ref | refs/heads/main |
| repository, if present | Artur0927/uptimeforge |
| repository_owner, if present | Artur0927 |
| repository_id, if present | 1412546510 |
| repository_owner_id, if present | 99685228 |

Missing required claims or any mismatched present claim print `FAIL <claim>`;
the remaining checks still run, followed by `FAIL claim_checks` and exit code 1.
For example, an unexpected subject prints `FAIL sub`, without printing its value.
Absent optional repository/owner claims print `SKIP <claim> (optional claim
absent)`. A successful run with SKIP does not verify the skipped identifiers.
Request/decoding errors print only a fixed, sanitized failure message and exit 1.

The subject is expected until this workflow runs successfully on main. GitHub
documents immutable subjects and the change in context when a job declares an
environment: [OIDC reference](https://docs.github.com/en/actions/reference/security/oidc).
This job intentionally declares no environment. Results are diagnostics of a
token requested directly from GitHub, not independent signature validation or
proof of AWS role assumption.

## Security review

- Only `workflow_dispatch` triggers the workflow; job and script both enforce
  the intended repository and main ref. The script also checks the manual event.
- Workflow-level permissions are empty. The single job grants only
  `id-token: write` and `contents: read`, with a three-minute timeout.
- Inline Python uses the standard library. No checkout, dependencies or third-party
  actions are executed, so there are no action versions requiring SHA pins.
- The audience is explicitly set to `sts.amazonaws.com`. Requests require HTTPS
  to a GitHub Actions endpoint; proxy inheritance and redirects are disabled to
  protect the bearer header. Responses are bounded and the request times out.
- The JWT is decoded only in memory. No raw JWT, authentication header, response
  body, token-controlled claim value or exception detail is logged or persisted.
  No artifact upload, output file or token-bearing shell argument is used.
- No AWS SDK/CLI, role assumption, static AWS credentials, ECR push or production
  deployment runs. No AWS resource, Terraform configuration/state or SCP changes.
  This does not require changing the AWS Free Plan; standard GitHub-hosted runner
  usage is subject to the repository's GitHub Actions allowance.

## Local validation on October 13, 2026

- Ruby Psych parsed the YAML successfully.
- Local structural checks verified the manual trigger, repository/main guard,
  job permissions, absence of environment and absence of external actions.
- Bash syntax and embedded Python compilation passed.
- Nine synthetic test groups passed, covering valid claims, each mismatched claim,
  required/optional omissions, invalid claim types, execution/endpoint guards,
  malformed/oversized responses and sanitized errors. All HTTP calls were mocked;
  no real token was requested. The test harness is temporary at
  `/tmp/uptimeforge-test-oidc.py` for this workspace session.
- The existing CI, Terraform state and Terraform variables have unchanged checksums.
- `actionlint` and `yamllint` were not installed; no Actionlint result is claimed.
- This change introduces no whitespace errors. The existing working tree has an
  unrelated trailing blank-line warning in `.gitignore`, which was preserved.

## ECR authentication next steps

1. Run these diagnostics after the reviewed merge; retain only the sanitized claim
   results as evidence. Resolve mismatches before changing IAM trust.
2. Obtain organization-approved OIDC inspection access under SCP `p-po1vubeu`.
   Claim verification does not establish provider existence, ownership or AWS
   permissions. Do not create a provider to work around the inspection denial.
3. Verify provider ownership/audience and review a later IAM plan with ECR already
   deployed. Keep live `enable_cicd_iam=false` until IAM deployment is separately
   approved; attaching the dedicated Docker profile remains another reviewed stage.
4. After approval, add an OIDC ECR publisher job to a separate change: run after
   tests on main, use temporary AWS credentials, and push the application image as
   `sha-<40-character-git-commit-sha>`. API and Worker use that same image. Preserve
   PostgreSQL's official image and persistent volume. Production SSM deployment
   remains separate from publisher authentication.
