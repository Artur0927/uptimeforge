output "nat_instance_id" {
  description = "Instance ID to use with Session Manager."
  value       = aws_instance.nat.id
}

output "nat_public_ip" {
  description = "Temporary public IP for outbound NAT traffic; can change on EC2 stop/start."
  value       = aws_instance.nat.public_ip
}

output "nginx_instance_id" {
  value = aws_instance.nginx.id
}

output "nginx_public_ip" {
  description = "Temporary public IPv4; HTTP (80) will serve a test page."
  value       = aws_instance.nginx.public_ip
}

output "nginx_test_url" {
  description = "HTTP-only first-boot smoke test."
  value       = "http://${aws_instance.nginx.public_ip}"
}

output "docker_instance_id" {
  value = aws_instance.docker_host.id
}

output "docker_private_ip" {
  value = aws_instance.docker_host.private_ip
}

output "aws_region" {
  description = "AWS_REGION for future GitHub Actions jobs."
  value       = var.aws_region
}

output "ecr_repository_url" {
  description = "Application image URL; append :sha-<full commit SHA> for API and Worker."
  value       = module.ecr.repository_url
}

output "ecr_repository_name" {
  description = "ECR_REPOSITORY for future GitHub Actions jobs."
  value       = module.ecr.repository_name
}

output "ecr_repository_arn" {
  description = "Private application repository ARN."
  value       = module.ecr.repository_arn
}

output "github_actions_role_arn" {
  description = "AWS_ROLE_ARN for future GitHub Actions OIDC authentication."
  value       = var.enable_cicd_iam ? module.iam[0].github_actions_role_arn : null
}

output "github_oidc_provider_arn" {
  description = "Account-wide GitHub OIDC provider ARN."
  value       = var.enable_cicd_iam ? module.iam[0].github_oidc_provider_arn : null
}

output "github_oidc_subject" {
  description = "Exact accepted main-branch OIDC subject."
  value       = var.enable_cicd_iam ? var.github_oidc_subject : null
}

output "docker_host_role_arn" {
  description = "Dedicated Docker Host SSM and ECR pull role."
  value       = var.enable_cicd_iam ? module.iam[0].docker_host_role_arn : null
}

output "docker_host_instance_profile_name" {
  description = "Prepared dedicated Docker Host profile; associating it with EC2 is a separate reviewed change."
  value       = var.enable_cicd_iam ? module.iam[0].docker_host_instance_profile_name : null
}
