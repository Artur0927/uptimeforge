variable "name_prefix" {
  description = "Project-environment prefix for new roles and profiles."
  type        = string
}

variable "repository_arn" {
  description = "The only ECR repository the GitHub publisher may push to."
  type        = string
}

variable "github_oidc_subject" {
  description = "Exact expected GitHub OIDC subject for the authorized branch; verify real Actions claims before deployment."
  type        = string

  validation {
    condition     = can(regex("^repo:[^:*?]+/[^:*?]+:ref:refs/heads/main$", var.github_oidc_subject))
    error_message = "Use an exact repository subject restricted to refs/heads/main, without wildcards."
  }
}

variable "create_github_oidc_provider" {
  description = "Manage the account-wide GitHub provider here, rather than reuse it. Import before adopting an existing provider."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Project and environment tags."
  type        = map(string)
  default     = {}
}
