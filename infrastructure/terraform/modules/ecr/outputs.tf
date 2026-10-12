output "repository_url" {
  description = "Repository URL without an image tag."
  value       = aws_ecr_repository.application.repository_url
}

output "repository_name" {
  description = "Private application repository name."
  value       = aws_ecr_repository.application.name
}

output "repository_arn" {
  description = "Repository ARN for IAM permissions."
  value       = aws_ecr_repository.application.arn
}
