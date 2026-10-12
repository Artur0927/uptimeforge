# Official AL2023 x86_64 AMI; evaluated in the AWS provider region.
data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

# Public NAT instance; initial user_data installs persistent Linux forwarding/NAT.
resource "aws_instance" "nat" {
  ami                         = data.aws_ssm_parameter.al2023.value
  instance_type               = var.nat_instance_type
  subnet_id                   = aws_subnet.public_a.id
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.nat.id]
  source_dest_check           = false
  iam_instance_profile        = aws_iam_instance_profile.ssm.name
  user_data = templatefile("${path.module}/bootstrap/nat.sh.tftpl", {
    private_subnet_cidr = aws_subnet.private_a.cidr_block
  })

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  credit_specification {
    cpu_credits = "standard"
  }

  root_block_device {
    volume_size = 8
    volume_type = "gp3"
    encrypted   = true
  }

  tags = {
    Name = "uptimeforge-nat"
  }

  # Public default route and SSM policy attachment should exist first.
  depends_on = [
    aws_route_table_association.public_a,
    aws_iam_role_policy_attachment.ssm,
  ]
}

# This route points private outbound IPv4 traffic to NAT instance's primary ENI.
# Local VPC traffic remains routed via the VPC's implicit local route.
resource "aws_route" "private_default" {
  route_table_id         = aws_route_table.private.id
  destination_cidr_block = "0.0.0.0/0"
  network_interface_id   = aws_instance.nat.primary_network_interface_id
}

# Public Nginx reverse proxy host. Bootstrap serves a harmless test page on HTTP/80.
# HTTPS/443 is deliberately NOT configured until a domain and TLS certificate exist.
resource "aws_instance" "nginx" {
  ami                         = data.aws_ssm_parameter.al2023.value
  instance_type               = var.nginx_instance_type
  subnet_id                   = aws_subnet.public_a.id
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.nginx.id]
  iam_instance_profile        = aws_iam_instance_profile.ssm.name
  user_data                   = file("${path.module}/bootstrap/nginx.sh")

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  credit_specification {
    cpu_credits = "standard"
  }

  root_block_device {
    volume_size = 8
    volume_type = "gp3"
    encrypted   = true
  }

  tags = {
    Name = "uptimeforge-nginx"
  }

  depends_on = [
    aws_route_table_association.public_a,
    aws_iam_role_policy_attachment.ssm,
  ]
}

# Private Docker host; no public IPv4. Next hands-on step: install Docker via SSM,
# then deploy FastAPI + Worker + Postgres with Compose (do NOT expose port 5432).
resource "aws_instance" "docker_host" {
  ami                         = data.aws_ssm_parameter.al2023.value
  instance_type               = var.docker_instance_type
  subnet_id                   = aws_subnet.private_a.id
  associate_public_ip_address = false
  vpc_security_group_ids      = [aws_security_group.docker_host.id]
  iam_instance_profile        = aws_iam_instance_profile.ssm.name

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  credit_specification {
    cpu_credits = "standard"
  }

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
    encrypted   = true
  }

  tags = {
    Name = "uptimeforge-docker-host"
  }

  # Can initiate SSM only when outbound HTTPS via NAT is available.
  depends_on = [
    aws_route.private_default,
    aws_route_table_association.private_a,
    aws_iam_role_policy_attachment.ssm,
  ]
}
