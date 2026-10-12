output "docker_host_role_arn" {
  description = "Dedicated SSM and ECR pull role."
  value       = aws_iam_role.docker_host.arn
}

output "docker_host_instance_profile_name" {
  description = "Docker Host profile; policies are attached before association."
  value       = aws_iam_instance_profile.docker_host.name
}
