# Change these after checking eu-north-1 pricing and your account limits.
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
