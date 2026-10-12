output "github_actions_role_arn" {
  description = "Role ARN for aws-actions/configure-aws-credentials."
  value       = aws_iam_role.github_actions.arn
}

output "github_oidc_provider_arn" {
  description = "Reused or managed account-wide GitHub OIDC provider."
  value       = local.oidc_provider_arn
}

output "docker_host_role_arn" {
  description = "Dedicated SSM and ECR pull role."
  value       = aws_iam_role.docker_host.arn
}

output "docker_host_instance_profile_name" {
  description = "Docker Host profile; policies are attached before association."
  value       = aws_iam_instance_profile.docker_host.name
}
