output "vpc_id" {
  description = "VPC created for the EKS lab."
  value       = aws_vpc.mlops.id
}

output "public_subnet_ids" {
  description = "IDs of the public subnets."
  value       = [for subnet in aws_subnet.public : subnet.id]
}

output "private_subnet_ids" {
  description = "IDs of the private subnets containing EKS workers."
  value       = [for subnet in aws_subnet.private : subnet.id]
}

output "nat_gateway_public_ip" {
  description = "Public NAT IP used for outbound traffic from private subnets."
  value       = aws_eip.nat.public_ip
}

output "eks_cluster_name" {
  description = "EKS cluster to use with aws eks update-kubeconfig."
  value       = aws_eks_cluster.mlops.name
}

output "eks_cluster_endpoint" {
  description = "API endpoint protected by the CIDR allowlist and IAM."
  value       = aws_eks_cluster.mlops.endpoint
}

output "eks_cluster_role_arn" {
  description = "IAM role assumed by the EKS control plane."
  value       = aws_iam_role.eks_cluster.arn
}

output "eks_node_role_arn" {
  description = "EC2 role for EKS managed worker nodes."
  value       = aws_iam_role.eks_nodes.arn
}
