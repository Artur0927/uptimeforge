variable "name_prefix" {
  description = "Project-environment prefix for the dedicated Docker Host role/profile."
  type        = string
}

variable "repository_arn" {
  description = "Only the existing UptimeForge repository may be pulled."
  type        = string

  validation {
    condition     = var.repository_arn == "arn:aws:ecr:eu-north-1:152680102458:repository/uptimeforge-api"
    error_message = "Docker Host pull access must target only the existing UptimeForge ECR repository."
  }
}

variable "tags" {
  description = "Project and environment tags."
  type        = map(string)
  default     = {}
}
