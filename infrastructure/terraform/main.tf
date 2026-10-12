# Keep the deployed network, EC2 and shared SSM resources at their root addresses.
# Only new infrastructure belongs to these modules; no state moves are needed.
locals {
  name_prefix = "${var.project}-${var.environment}"
  tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

module "ecr" {
  source = "./modules/ecr"

  repository_name     = "uptimeforge-api"
  release_image_count = var.ecr_release_image_count
  tags                = local.tags
}

module "iam" {
  source = "./modules/iam"
  count  = var.enable_cicd_iam ? 1 : 0

  name_prefix                 = local.name_prefix
  repository_arn              = module.ecr.repository_arn
  github_oidc_subject         = var.github_oidc_subject
  create_github_oidc_provider = var.create_github_oidc_provider
  tags                        = local.tags
}

# Host-only IAM never evaluates GitHub OIDC data or resources.
module "docker_host_iam" {
  source = "./modules/docker-host-iam"
  count  = var.enable_docker_host_iam ? 1 : 0

  name_prefix    = local.name_prefix
  repository_arn = module.ecr.repository_arn
  tags           = local.tags
}
