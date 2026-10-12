variable "aws_region" {
  description = "Region of the existing deployment; network AZs are fixed to eu-north-1."
  type        = string
  default     = "eu-north-1"

  validation {
    condition     = var.aws_region == "eu-north-1"
    error_message = "This live stack must remain in eu-north-1."
  }
}

variable "aws_profile" {
  description = "Local AWS CLI profile. Set to null to use the default credential chain."
  type        = string
  default     = "uptimeforge"
}

variable "project" {
  description = "Project name for new resource names and tags."
  type        = string
  default     = "uptimeforge"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,23}$", var.project))
    error_message = "Use a lowercase project name of at most 24 characters."
  }
}

variable "environment" {
  description = "Infrastructure environment for new resources; dev matches existing IAM names."
  type        = string
  default     = "dev"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,15}$", var.environment))
    error_message = "Use a lowercase environment name of at most 16 characters."
  }
}

variable "ecr_release_image_count" {
  description = "Number of recent sha-<full commit SHA> release images to retain."
  type        = number
  default     = 20

  validation {
    condition     = var.ecr_release_image_count >= 1 && floor(var.ecr_release_image_count) == var.ecr_release_image_count
    error_message = "Release image retention must be a positive integer."
  }
}

variable "enable_cicd_iam" {
  description = "Enable only GitHub publisher IAM and OIDC. Independent Docker Host IAM/profile migration uses separate flags."
  type        = bool
  default     = false
}

variable "github_oidc_subject" {
  description = "Expected immutable main-branch subject; verify against real Actions OIDC claims before deployment. Jobs must not set an environment."
  type        = string
  default     = "repo:Artur0927@99685228/uptimeforge@1412546510:ref:refs/heads/main"

  validation {
    condition     = var.github_oidc_subject == "repo:Artur0927@99685228/uptimeforge@1412546510:ref:refs/heads/main"
    error_message = "Trust must match the expected immutable Artur0927/uptimeforge main-branch subject. Verify real Actions OIDC claims before deployment."
  }
}

variable "create_github_oidc_provider" {
  description = "False reuses the account's GitHub provider. True manages it here; verify absence or import it before applying."
  type        = bool
  default     = false
}

# Existing instance sizes remain unchanged.
variable "nat_instance_type" {
  description = "Small x86_64 EC2 for Linux NAT."
  type        = string
  default     = "t3.micro"
}

variable "nginx_instance_type" {
  description = "Small x86_64 EC2 for reverse proxy."
  type        = string
  default     = "t3.micro"
}

variable "docker_instance_type" {
  description = "Private host for Docker Compose; 2 GiB RAM may be tight for the full app."
  type        = string
  default     = "t3.small"
}

variable "enable_docker_host_iam" {
  description = "Create only the dedicated SSM/ECR pull role and profile; does not associate it to EC2."
  type        = bool
  default     = false
}

variable "associate_docker_host_profile" {
  description = "Separately approved in-place Docker Host profile migration; requires enable_docker_host_iam=true."
  type        = bool
  default     = false
}
