data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  github_issuer       = "token.actions.githubusercontent.com"
  github_provider_arn = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/${local.github_issuer}"
  oidc_provider_arn   = var.create_github_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : data.aws_iam_openid_connect_provider.github[0].arn
}

# Lookup fails closed if the account-wide provider does not exist or cannot be read.
data "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 0 : 1
  arn   = local.github_provider_arn

  lifecycle {
    postcondition {
      condition     = contains(self.client_id_list, "sts.amazonaws.com")
      error_message = "The existing GitHub provider must allow audience sts.amazonaws.com."
    }
  }
}

resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 1 : 0

  url            = "https://${local.github_issuer}"
  client_id_list = ["sts.amazonaws.com"]
  # AWS verifies GitHub through its trusted CA library; no stale thumbprint pins.
  tags = merge(var.tags, { Name = "github-actions" })

  lifecycle {
    prevent_destroy = true
  }
}

data "aws_iam_policy_document" "github_trust" {
  statement {
    sid     = "GitHubMainBranch"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.github_issuer}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.github_issuer}:sub"
      values   = [var.github_oidc_subject]
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name                 = "${var.name_prefix}-github-ecr-push-role"
  description          = "GitHub Actions main-branch image publishing to UptimeForge ECR"
  assume_role_policy   = data.aws_iam_policy_document.github_trust.json
  max_session_duration = 3600
  tags                 = merge(var.tags, { Name = "${var.name_prefix}-github-ecr-push-role" })
}

data "aws_iam_policy_document" "ecr_push" {
  statement {
    sid       = "RegistryAuthentication"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"] # This API does not support repository-level permissions.
  }

  statement {
    sid = "PushApplicationImage"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    resources = [var.repository_arn]
  }
}

resource "aws_iam_role_policy" "github_ecr_push" {
  name   = "${var.name_prefix}-ecr-push"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.ecr_push.json
}
