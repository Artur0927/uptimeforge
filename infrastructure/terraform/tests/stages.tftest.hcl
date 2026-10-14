# Root composition regression tests. Mocked AWS performs no cloud API calls.
mock_provider "aws" {
  mock_data "aws_ssm_parameter" {
    defaults = { value = "ami-0123456789abcdef0" }
  }
  mock_data "aws_partition" {
    defaults = { partition = "aws" }
  }
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
  }
  mock_data "aws_iam_policy_document" {
    defaults = {
      json = jsonencode({
        Version   = "2012-10-17"
        Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "ec2.amazonaws.com" } }]
      })
    }
  }
  mock_data "aws_iam_openid_connect_provider" {
    defaults = {
      arn            = "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
      client_id_list = ["sts.amazonaws.com"]
    }
  }
}

run "ecr_only_by_default" {
  command = plan

  assert {
    condition = alltrue([
      for instance in [aws_instance.nat, aws_instance.nginx, aws_instance.docker_host] :
      instance.ami == "ami-01e082ac2f79f3918"
    ])
    error_message = "Unrelated changes must preserve the deployed AMI, not adopt the moving latest lookup."
  }

  assert {
    condition     = length(module.iam) == 0 && length(module.docker_host_iam) == 0
    error_message = "Default composition must instantiate no IAM module or OIDC lookups."
  }
  assert {
    condition = (
      output.github_actions_role_arn == null &&
      output.github_oidc_provider_arn == null &&
      output.github_oidc_subject == null &&
      output.docker_host_role_arn == null &&
      output.docker_host_instance_profile_name == null
    )
    error_message = "Optional IAM outputs must be null when the module is disabled."
  }
  assert {
    condition = (
      aws_instance.docker_host.iam_instance_profile == aws_iam_instance_profile.ssm.name &&
      aws_instance.nat.iam_instance_profile == aws_iam_instance_profile.ssm.name &&
      aws_instance.nginx.iam_instance_profile == aws_iam_instance_profile.ssm.name
    )
    error_message = "The ECR-only phase must preserve all three shared SSM profile associations."
  }
  assert {
    condition     = output.ecr_repository_name == "uptimeforge-api"
    error_message = "The ECR module must remain available independently of IAM."
  }
}

run "iam_opt_in_preserves_compute" {
  command = plan

  variables {
    enable_cicd_iam = true
  }

  assert {
    condition     = length(module.iam) == 1
    error_message = "Explicit opt-in must instantiate the prepared IAM module."
  }
  assert {
    condition = (
      aws_instance.docker_host.iam_instance_profile == aws_iam_instance_profile.ssm.name &&
      aws_instance.nat.iam_instance_profile == aws_iam_instance_profile.ssm.name &&
      aws_instance.nginx.iam_instance_profile == aws_iam_instance_profile.ssm.name
    )
    error_message = "Creating future IAM infrastructure must preserve all three shared SSM profile associations."
  }
  assert {
    condition     = output.ecr_repository_name == "uptimeforge-api"
    error_message = "Enabling IAM must preserve the same ECR module and repository."
  }
}

run "host_iam_only_preserves_all_profiles" {
  command = plan
  variables {
    enable_docker_host_iam = true
    enable_cicd_iam        = false
  }
  override_resource {
    target = module.ecr.aws_ecr_repository.application
    values = { arn = "arn:aws:ecr:eu-north-1:152680102458:repository/uptimeforge-api" }
  }
  assert {
    condition     = length(module.iam) == 0 && length(module.docker_host_iam) == 1
    error_message = "Host-only IAM must never enable GitHub/OIDC."
  }
  assert {
    condition = (
      aws_instance.docker_host.iam_instance_profile == aws_iam_instance_profile.ssm.name &&
      aws_instance.nat.iam_instance_profile == aws_iam_instance_profile.ssm.name &&
      aws_instance.nginx.iam_instance_profile == aws_iam_instance_profile.ssm.name
    )
    error_message = "Role creation alone must not change any existing EC2 profile."
  }
}

run "approved_host_profile_only" {
  command = plan
  variables {
    enable_docker_host_iam        = true
    associate_docker_host_profile = true
    enable_cicd_iam               = false
  }
  override_resource {
    target = module.ecr.aws_ecr_repository.application
    values = { arn = "arn:aws:ecr:eu-north-1:152680102458:repository/uptimeforge-api" }
  }
  assert {
    condition = (
      length(module.iam) == 0 &&
      aws_instance.docker_host.iam_instance_profile == module.docker_host_iam[0].docker_host_instance_profile_name &&
      aws_instance.nat.iam_instance_profile == aws_iam_instance_profile.ssm.name &&
      aws_instance.nginx.iam_instance_profile == aws_iam_instance_profile.ssm.name
    )
    error_message = "Explicit migration may select only Docker Host's dedicated profile."
  }
}

run "reject_profile_without_role" {
  command = plan
  variables { associate_docker_host_profile = true }
  expect_failures = [aws_instance.docker_host]
}
