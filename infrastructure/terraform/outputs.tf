output "nat_instance_id" {
  description = "Instance ID to use with Session Manager."
  value       = aws_instance.nat.id
}

output "nat_public_ip" {
  description = "Temporary public IP for outbound NAT traffic; can change on EC2 stop/start."
  value       = aws_instance.nat.public_ip
}

output "nginx_instance_id" {
  value = aws_instance.nginx.id
}

output "nginx_public_ip" {
  description = "Temporary public IPv4; HTTP (80) will serve a test page."
  value       = aws_instance.nginx.public_ip
}

output "nginx_test_url" {
  description = "HTTP-only first-boot smoke test."
  value       = "http://${aws_instance.nginx.public_ip}"
}

output "docker_instance_id" {
  value = aws_instance.docker_host.id
}

output "docker_private_ip" {
  value = aws_instance.docker_host.private_ip
}
