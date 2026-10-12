data "aws_iam_policy_document" "ec2_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "docker_host" {
  name               = "${var.name_prefix}-docker-host-role"
  description        = "Private Docker Host: SSM access and repository-scoped ECR pull"
  assume_role_policy = data.aws_iam_policy_document.ec2_trust.json
  tags               = merge(var.tags, { Name = "${var.name_prefix}-docker-host-role" })
}

resource "aws_iam_role_policy_attachment" "docker_host_ssm" {
  role       = aws_iam_role.docker_host.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "aws_iam_policy_document" "ecr_pull" {
  statement {
    sid       = "RegistryAuthentication"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "PullApplicationImage"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
    resources = [var.repository_arn]
  }
}

resource "aws_iam_role_policy" "docker_host_ecr_pull" {
  name   = "${var.name_prefix}-ecr-pull"
  role   = aws_iam_role.docker_host.id
  policy = data.aws_iam_policy_document.ecr_pull.json
}

resource "aws_iam_instance_profile" "docker_host" {
  name = "${var.name_prefix}-docker-host-profile"
  role = aws_iam_role.docker_host.name
  tags = merge(var.tags, { Name = "${var.name_prefix}-docker-host-profile" })

  depends_on = [
    aws_iam_role_policy_attachment.docker_host_ssm,
    aws_iam_role_policy.docker_host_ecr_pull,
  ]
}
