# Docker Host ECR pull role and profile migration

This runbook prepares two separately approved changes for account 152680102458,
region eu-north-1. It does not authorize an apply or an EC2 profile change.
Keep enable_cicd_iam=false and create_github_oidc_provider=false. No GitHub
provider, token or SCP change is needed for EC2 instance credentials.

## Configuration and resource ownership

| Stage | enable_docker_host_iam | associate_docker_host_profile | Expected managed changes |
| --- | --- | --- | --- |
| Default | false | false | None |
| Approved IAM preparation | true | false | Four IAM creates; existing resources unchanged |
| Approved profile migration after IAM exists | true | true | One in-place Docker Host profile update only |
| Approved profile rollback | true | false | One in-place update back to the shared SSM profile |

The four new addresses are:

```text
module.docker_host_iam[0].aws_iam_role.docker_host
module.docker_host_iam[0].aws_iam_role_policy_attachment.docker_host_ssm
module.docker_host_iam[0].aws_iam_role_policy.docker_host_ecr_pull
module.docker_host_iam[0].aws_iam_instance_profile.docker_host
```

Their names use uptimeforge-dev: role uptimeforge-dev-docker-host-role,
profile uptimeforge-dev-docker-host-profile, inline policy uptimeforge-dev-ecr-pull.
The role trusts only ec2.amazonaws.com through sts:AssumeRole. It retains
AmazonSSMManagedInstanceCore and permits GetAuthorizationToken on * (required
by this API), plus BatchCheckLayerAvailability, BatchGetImage and
GetDownloadUrlForLayer only on
arn:aws:ecr:eu-north-1:152680102458:repository/uptimeforge-api. No push, OIDC,
NAT/Nginx permissions or secret distribution are added.

All existing managed addresses, including aws_instance.docker_host,
aws_instance.nat, aws_instance.nginx, root shared SSM resources and module.ecr,
remain unchanged. NAT/Nginx always use aws_iam_instance_profile.ssm. The new
profile depends on its SSM attachment and pull policy before association.

The former optional IAM module had no deployed resources in the reviewed local
state; its undeployed host definitions were extracted into the independent
module. GitHub publisher addresses remain unchanged. If another backend/state
has deployed the former module.iam host resources or these IAM names already
exist, stop for ownership review. Do not create duplicates, import or move state
under this runbook. Never enable both old and new host definitions from different
configuration versions.

## Permissions and billing prerequisites

Use an approved short-lived human session, such as an already authorized SSO
profile. Do not copy permanent credentials to GitHub or EC2. Verify the actual
account and operator role. An AssumeRole profile whose source uses static keys
does not satisfy the manual release's keyless-source requirement.

The organization/security owner must approve the Terraform operator's effective
permissions, including applicable SCPs and permission boundaries:

- Initial IAM writes: CreateRole, TagRole, PutRolePolicy, AttachRolePolicy,
  CreateInstanceProfile, TagInstanceProfile and AddRoleToInstanceProfile, scoped
  to the exact dedicated role/profile ARNs where AWS supports resource scoping.
  Constrain AttachRolePolicy to AmazonSSMManagedInstanceCore with iam:PolicyARN.
- IAM refresh/read: GetRole, GetRolePolicy, ListRolePolicies,
  ListAttachedRolePolicies, GetInstanceProfile and relevant tag reads. Scope to
  these dedicated resources and existing shared resources as needed for refresh.
- iam:PassRole on the dedicated role for preparation/association, and on the
  original shared role for rollback. Restrict iam:PassedToService to
  ec2.amazonaws.com; do not grant PassRole on *.
- Association: ec2:ReplaceIamInstanceProfileAssociation on only the existing
  Docker Host instance. The pinned provider uses replacement when an association
  exists. AssociateIamInstanceProfile is needed only if inspection establishes
  that no association exists; that unexpected state needs separate review.
  Require a running, stable instance with its existing association before migration.
  The pinned provider can disassociate/reassociate a stopped instance; stop review
  if the host is stopped or stopping. Normal running-host migration does not
  require DisassociateIamInstanceProfile, RunInstances,
  TerminateInstances, StopInstances or StartInstances.
- Read-only EC2 DescribeInstances/DescribeIamInstanceProfileAssociations and
  relevant network/volume/security-group reads for the existing stack. AWS describe
  APIs often require *. Restrict requested region where supported. SSM GetParameter
  for the existing AMI lookup and existing ECR refresh reads are still required
  for a future real plan; this change does not bypass them.
- SSM: approved StartSession access to the exact Docker Host and required session
  document, plus DescribeInstanceInformation and session ownership/status access.
  Rollback operator access must remain usable independently of host SSM health.

These are a review checklist, not a policy granting access. Confirm full provider
refresh permissions and organizational controls before a live plan. Do not modify
SCP p-po1vubeu or request OIDC inspection permission for host-only IAM.

IAM preparation adds no compute, storage, endpoints or paid services. Existing
EC2, EBS, ECR, IPv4 and transfer usage can still consume credits/incur costs.
The billing owner must confirm actual plan, credits and expiry. AWS documents
that Organizations enrollment upgrades a Free plan to Paid; do not claim strict
Free Plan compatibility for this organization-managed account without verifying
that discrepancy. No billing or organization change is authorized.

References: [EC2 role attachment permissions](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/permission-to-pass-iam-roles.html),
[ECR action scopes](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ecr.html),
[instance profile propagation](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_switch-role-ec2_instance-profiles.html),
[AWS account plans](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html).

## Plan review and approval gates

Run local checks first from infrastructure/terraform:

```bash
terraform fmt -recursive -check
terraform init -backend=false -input=false -lockfile=readonly
terraform validate
terraform test -no-color
```

The contracts use mocks/synthetic credentials and plan only; they never apply.
They cover pull scopes/trust, non-UptimeForge repository rejection, OIDC isolation,
unchanged profiles, explicit host migration and rejection of migration without IAM.

A future live plan requires read-only access approval and current backend/state
ownership checks. This task does not run it. Store plan files privately outside
Git because they may contain sensitive values. Review the full plan, not only a
resource count. The existing moving SSM latest AMI can introduce replacements;
stop on any such drift and resolve it in a separate reviewed change. Do not use
-target, ignore_changes or refresh=false to hide live drift in an approval plan.

Example future preparation plan (read-only, with approved temporary credentials):

```bash
terraform plan -input=false -var=aws_profile=APPROVED_TEMP_PROFILE \
  -var=enable_cicd_iam=false \
  -var=enable_docker_host_iam=true -var=associate_docker_host_profile=false \
  -out=/PRIVATE_PLAN_DIRECTORY/host-iam.tfplan
terraform show -json /PRIVATE_PLAN_DIRECTORY/host-iam.tfplan | \
  python ../../scripts/verify-docker-host-iam-plan.py prepare
```

Require exactly four IAM creates, zero replacements/deletes, and no changes to
existing EC2, networking, shared SSM, ECR or associations. Obtain Tech Lead and
organization approval before the separate IAM creation operation. This preparation
PR stops before that operation.

After approved IAM creation, keep enable_docker_host_iam=true in private variables
and associate_docker_host_profile=false. Inspect role trust/policies and profile
membership with approved IAM read APIs; wait for propagation. Keep the original
shared SSM profile and both roles available for rollback. Do not disable host IAM
to roll back a profile: that would propose deleting the dedicated resources.

## Separately approved Docker Host migration

1. Record Docker Host instance ID, current association ID, instance profile name,
   both profile ARNs and the original shared role. Inspect the real EC2 association:

   ```bash
   aws sts get-caller-identity --profile APPROVED_TEMP_PROFILE
   aws ec2 describe-iam-instance-profile-associations --region eu-north-1 \
     --profile APPROVED_TEMP_PROFILE \
     --filters Name=instance-id,Values=DOCKER_HOST_INSTANCE_ID
   aws ssm describe-instance-information --region eu-north-1 \
     --profile APPROVED_TEMP_PROFILE \
     --filters Key=InstanceIds,Values=DOCKER_HOST_INSTANCE_ID
   ```

2. Confirm SSM reports Online and open a fresh baseline SSM session. On the host
   verify IMDSv2, no credential environment overrides/static-key files, and
   aws sts get-caller-identity using only instance credentials. Do not print IMDS
   credential documents. Check running API/Worker/database health and host egress.
3. Review a fresh plan with enable_docker_host_iam=true,
   associate_docker_host_profile=true and enable_cicd_iam=false. The four IAM
   resources must already exist: expect zero creates, one in-place
   aws_instance.docker_host.iam_instance_profile update and zero other changes.
   Pass its private JSON through verify-docker-host-iam-plan.py migrate.
4. Obtain explicit approval for the profile migration, schedule observation and
   have a control-plane rollback operator available. Execute only the reviewed
   association change in that separate authorized operation. No EC2 recreation,
   reboot, app deployment or database migration is required by the profile change.
5. Allow IAM/instance credential propagation; cached credentials may retain the
   old role temporarily. Recheck actual association/role and open a **new** SSM
   session, rather than relying on one that was already connected. Confirm Online
   status, account 152680102458 and assumed role uptimeforge-dev-docker-host-role.
6. Test the role's ECR login using password-stdin or an approved credential helper,
   then pull a known existing immutable SHA image. Use a temporary protected Docker
   credential configuration if needed; never print the token. A pull is a registry
   read, but is still a separately approved host verification, not a deployment.
   Do not start/recreate containers as part of IAM verification. Verify NAT/Nginx
   associations and SSM remain unchanged.

## Rollback and SSM loss

Keep dedicated IAM enabled. Set only associate_docker_host_profile=false, review
a fresh rollback plan and require exactly one in-place Docker Host update to
uptimeforge-dev-ec2-ssm-profile. Check its JSON with the rollback mode. Rollback
itself requires explicit authorization; do not automatically revert on a timeout.

If SSM is lost, the independently authorized control-plane operator can inspect
and replace the association back to the recorded original profile without needing
a host session. This emergency command is for a separately approved rollback only:

```bash
aws ec2 replace-iam-instance-profile-association --region eu-north-1 \
  --profile APPROVED_TEMP_PROFILE --association-id CURRENT_ASSOCIATION_ID \
  --iam-instance-profile Name=uptimeforge-dev-ec2-ssm-profile
```

Reinspect the association, wait for credentials to propagate and verify SSM Online
plus a new session. If that approved emergency change occurred outside Terraform,
set the migration flag false and review a normal refreshed plan to reconcile the
configuration; do not edit state. NAT/Nginx, images, applications and database
volumes are unaffected. Do not remove shared-role SSM permissions, install static
keys, open SSH or stop/start the host as an automatic workaround.
