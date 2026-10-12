# UptimeForge v1 — AWS network (eu-north-1)
# Planned only. Do not apply until EC2 design, costs and security are reviewed.

# -----------------------------------------------------------------------------
# VPC and subnets
# -----------------------------------------------------------------------------
resource "aws_vpc" "main" {
  cidr_block           = "10.20.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "uptimeforge-dev-vpc"
  }
}

resource "aws_subnet" "public_a" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.20.1.0/24"
  availability_zone = "eu-north-1a"

  tags = {
    Name = "uptimeforge-public-a"
  }
}

resource "aws_subnet" "private_a" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.20.2.0/24"
  availability_zone = "eu-north-1a"

  tags = {
    Name = "uptimeforge-private-a"
  }
}

# -----------------------------------------------------------------------------
# Internet gateway and routing
# -----------------------------------------------------------------------------
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "uptimeforge-dev-igw"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "uptimeforge-public-rt"
  }
}

resource "aws_route_table_association" "public_a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  # No default internet route yet. Later: 0.0.0.0/0 -> NAT ENI.
  tags = {
    Name = "uptimeforge-private-rt"
  }
}

resource "aws_route_table_association" "private_a" {
  subnet_id      = aws_subnet.private_a.id
  route_table_id = aws_route_table.private.id
}

# -----------------------------------------------------------------------------
# Security groups (assigned to EC2 network interfaces at deployment)
# -----------------------------------------------------------------------------
resource "aws_security_group" "nginx" {
  name        = "uptimeforge-nginx-sg"
  description = "Security group for Nginx reverse proxy"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "uptimeforge-nginx-sg"
  }
}

resource "aws_security_group" "docker_host" {
  name        = "uptimeforge-docker-host-sg"
  description = "Security group for private Docker host"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "uptimeforge-docker-host-sg"
  }
}

resource "aws_security_group" "nat" {
  name        = "uptimeforge-nat-sg"
  description = "Security group for Linux NAT instance"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "uptimeforge-nat-sg"
  }
}

# -----------------------------------------------------------------------------
# Nginx: public HTTP/HTTPS; outbound to private API and for ACME/updates
# -----------------------------------------------------------------------------
resource "aws_vpc_security_group_ingress_rule" "nginx_http" {
  security_group_id = aws_security_group.nginx.id
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_ingress_rule" "nginx_https" {
  security_group_id = aws_security_group.nginx.id
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_egress_rule" "nginx_to_api" {
  security_group_id            = aws_security_group.nginx.id
  referenced_security_group_id = aws_security_group.docker_host.id
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
}

resource "aws_vpc_security_group_egress_rule" "nginx_http_to_internet" {
  security_group_id = aws_security_group.nginx.id
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_egress_rule" "nginx_https_to_internet" {
  security_group_id = aws_security_group.nginx.id
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
}

# -----------------------------------------------------------------------------
# Private Docker host: accepts API traffic only from the Nginx SG
# -----------------------------------------------------------------------------
resource "aws_vpc_security_group_ingress_rule" "api_from_nginx" {
  security_group_id            = aws_security_group.docker_host.id
  referenced_security_group_id = aws_security_group.nginx.id
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
}

resource "aws_vpc_security_group_egress_rule" "docker_http" {
  security_group_id = aws_security_group.docker_host.id
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_egress_rule" "docker_https" {
  security_group_id = aws_security_group.docker_host.id
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
}

# -----------------------------------------------------------------------------
# Linux NAT EC2: forwards HTTP/HTTPS traffic from the private subnet
# -----------------------------------------------------------------------------
resource "aws_vpc_security_group_ingress_rule" "nat_http_from_private" {
  security_group_id = aws_security_group.nat.id
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
  cidr_ipv4         = "10.20.2.0/24"
}

resource "aws_vpc_security_group_ingress_rule" "nat_https_from_private" {
  security_group_id = aws_security_group.nat.id
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "10.20.2.0/24"
}

resource "aws_vpc_security_group_egress_rule" "nat_http_to_internet" {
  security_group_id = aws_security_group.nat.id
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_egress_rule" "nat_https_to_internet" {
  security_group_id = aws_security_group.nat.id
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
}
