# Plan-only tests. Synthetic credentials and overrides prevent AWS API calls.
# Terraform >= 1.7 is required for override_data / override_resource.
provider "aws" {
  alias                       = "offline"
  region                      = "eu-north-1"
  access_key                  = "terraform-plan-test"
  secret_key                  = "terraform-plan-test"
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
}

run "ecr_release_contract" {
  command = plan
  module { source = "./modules/ecr" }
  providers = { aws = aws.offline }

  variables {
    repository_name = "uptimeforge-api"
    tags            = { Project = "uptimeforge", Environment = "dev" }
  }

  assert {
    condition = (
      aws_ecr_repository.application.image_tag_mutability == "IMMUTABLE" &&
      aws_ecr_repository.application.image_scanning_configuration[0].scan_on_push &&
      one(aws_ecr_repository.application.encryption_configuration).encryption_type == "AES256" &&
      !aws_ecr_repository.application.force_delete
    )
    error_message = "Release images must be immutable, scanned, encrypted and protected from forced deletion."
  }

  assert {
    condition = (
      jsondecode(aws_ecr_lifecycle_policy.application.policy).rules[0].selection.countNumber == 20 &&
      jsondecode(aws_ecr_lifecycle_policy.application.policy).rules[0].selection.tagPrefixList[0] == "sha-" &&
      jsondecode(aws_ecr_lifecycle_policy.application.policy).rules[1].selection.tagStatus == "untagged"
    )
    error_message = "Retention must cover SHA release images and untagged artifacts."
  }
}

run "reuse_provider_least_privilege" {
  command = plan
  module { source = "./modules/iam" }
  providers = { aws = aws.offline }

  variables {
    name_prefix         = "uptimeforge-dev"
    repository_arn      = "arn:aws:ecr:eu-north-1:123456789012:repository/uptimeforge-api"
    github_oidc_subject = "repo:Artur0927@99685228/uptimeforge@1412546510:ref:refs/heads/main"
  }

  override_data {
    target = data.aws_caller_identity.current
    values = { account_id = "123456789012" }
  }
  override_data {
    target = data.aws_iam_openid_connect_provider.github[0]
    values = {
      arn            = "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
      client_id_list = ["sts.amazonaws.com"]
      url            = "token.actions.githubusercontent.com"
    }
  }

  assert {
    condition = (
      length(aws_iam_openid_connect_provider.github) == 0 &&
      jsondecode(aws_iam_role.github_actions.assume_role_policy).Statement[0].Condition.StringEquals["token.actions.githubusercontent.com:sub"] == var.github_oidc_subject &&
      jsondecode(aws_iam_role.github_actions.assume_role_policy).Statement[0].Condition.StringEquals["token.actions.githubusercontent.com:aud"] == "sts.amazonaws.com" &&
      jsondecode(aws_iam_role.github_actions.assume_role_policy).Statement[0].Action == "sts:AssumeRoleWithWebIdentity" &&
      jsondecode(aws_iam_role.github_actions.assume_role_policy).Statement[0].Principal.Federated == "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
    )
    error_message = "Reuse the account provider and trust only the exact immutable main subject and STS audience."
  }

  assert {
    condition = (
      jsondecode(aws_iam_role_policy.github_ecr_push.policy).Statement[0].Action == "ecr:GetAuthorizationToken" &&
      jsondecode(aws_iam_role_policy.github_ecr_push.policy).Statement[0].Resource == "*" &&
      jsondecode(aws_iam_role_policy.github_ecr_push.policy).Statement[1].Resource == var.repository_arn &&
      toset(jsondecode(aws_iam_role_policy.github_ecr_push.policy).Statement[1].Action) == toset([
        "ecr:BatchCheckLayerAvailability", "ecr:BatchGetImage", "ecr:CompleteLayerUpload",
        "ecr:InitiateLayerUpload", "ecr:PutImage", "ecr:UploadLayerPart"
      ])
    )
    error_message = "Publishing permissions must be scoped to one repository, with only authentication on *."
  }

  assert {
    condition = (
      jsondecode(aws_iam_role_policy.docker_host_ecr_pull.policy).Statement[0].Action == "ecr:GetAuthorizationToken" &&
      jsondecode(aws_iam_role_policy.docker_host_ecr_pull.policy).Statement[0].Resource == "*" &&
      jsondecode(aws_iam_role_policy.docker_host_ecr_pull.policy).Statement[1].Resource == var.repository_arn &&
      toset(jsondecode(aws_iam_role_policy.docker_host_ecr_pull.policy).Statement[1].Action) == toset([
        "ecr:BatchCheckLayerAvailability", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"
      ]) &&
      aws_iam_role_policy_attachment.docker_host_ssm.policy_arn == "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
    )
    error_message = "Docker Host must retain SSM and may only pull from the application repository."
  }
}

run "reject_provider_without_sts_audience" {
  command = plan
  module { source = "./modules/iam" }
  providers = { aws = aws.offline }

  variables {
    name_prefix         = "uptimeforge-dev"
    repository_arn      = "arn:aws:ecr:eu-north-1:123456789012:repository/uptimeforge-api"
    github_oidc_subject = "repo:Artur0927@99685228/uptimeforge@1412546510:ref:refs/heads/main"
  }

  override_data {
    target = data.aws_caller_identity.current
    values = { account_id = "123456789012" }
  }
  override_data {
    target = data.aws_iam_openid_connect_provider.github[0]
    values = {
      arn            = "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
      client_id_list = ["unrelated-audience"]
      url            = "token.actions.githubusercontent.com"
    }
  }

  expect_failures = [data.aws_iam_openid_connect_provider.github]
}

run "manage_provider" {
  command = plan
  module { source = "./modules/iam" }
  providers = { aws = aws.offline }

  variables {
    name_prefix                 = "uptimeforge-dev"
    repository_arn              = "arn:aws:ecr:eu-north-1:123456789012:repository/uptimeforge-api"
    github_oidc_subject         = "repo:Artur0927@99685228/uptimeforge@1412546510:ref:refs/heads/main"
    create_github_oidc_provider = true
  }

  override_data {
    target = data.aws_caller_identity.current
    values = { account_id = "123456789012" }
  }
  override_resource {
    target = aws_iam_openid_connect_provider.github[0]
    values = { arn = "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com" }
  }

  assert {
    condition = (
      length(data.aws_iam_openid_connect_provider.github) == 0 &&
      aws_iam_openid_connect_provider.github[0].url == "https://token.actions.githubusercontent.com" &&
      toset(aws_iam_openid_connect_provider.github[0].client_id_list) == toset(["sts.amazonaws.com"])
    )
    error_message = "Manage exactly one GitHub issuer with the STS audience when explicitly requested."
  }
}

run "reject_wildcard_subject" {
  command = plan
  module { source = "./modules/iam" }
  providers = { aws = aws.offline }

  variables {
    name_prefix                 = "uptimeforge-dev"
    repository_arn              = "arn:aws:ecr:eu-north-1:123456789012:repository/uptimeforge-api"
    github_oidc_subject         = "repo:Artur0927/*:ref:refs/heads/main"
    create_github_oidc_provider = true
  }

  override_data {
    target = data.aws_caller_identity.current
    values = { account_id = "123456789012" }
  }
  expect_failures = [var.github_oidc_subject]
}
