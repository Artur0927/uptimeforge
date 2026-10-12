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
    condition     = length(module.iam) == 0
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
