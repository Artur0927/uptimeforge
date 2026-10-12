output "github_actions_role_arn" {
  description = "Role ARN for aws-actions/configure-aws-credentials."
  value       = aws_iam_role.github_actions.arn
}

output "github_oidc_provider_arn" {
  description = "Reused or managed account-wide GitHub OIDC provider."
  value       = local.oidc_provider_arn
}
