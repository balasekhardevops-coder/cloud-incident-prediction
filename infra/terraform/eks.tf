resource "aws_eks_cluster" "mlops" {
  name     = local.eks_cluster_name
  role_arn = aws_iam_role.eks_cluster.arn
  version  = var.eks_kubernetes_version

  access_config {
    authentication_mode                         = "API_AND_CONFIG_MAP"
    bootstrap_cluster_creator_admin_permissions = true
  }

  vpc_config {
    subnet_ids              = [for subnet in aws_subnet.private : subnet.id]
    endpoint_private_access = true
    endpoint_public_access  = true
    public_access_cidrs     = var.eks_public_access_cidrs
  }

  # Cluster cannot be created until its IAM role has the required policy.
  depends_on = [aws_iam_role_policy_attachment.eks_cluster]

  tags = { Name = local.eks_cluster_name }
}

resource "aws_eks_node_group" "mlops" {
  cluster_name    = aws_eks_cluster.mlops.name
  node_group_name = "${var.project_name}-${var.environment}-workers"
  node_role_arn   = aws_iam_role.eks_nodes.arn
  subnet_ids      = [for subnet in aws_subnet.private : subnet.id]

  instance_types = var.eks_node_instance_types
  capacity_type  = "ON_DEMAND"
  disk_size      = 30

  scaling_config {
    desired_size = var.eks_node_desired_size
    min_size     = 1
    max_size     = 3
  }

  update_config {
    max_unavailable = 1
  }

  # Wait for IAM permissions and private internet egress before bootstrapping.
  depends_on = [
    aws_iam_role_policy_attachment.eks_worker_node,
    aws_iam_role_policy_attachment.eks_ecr_pull,
    aws_iam_role_policy_attachment.eks_cni,
    aws_route.private_egress,
    aws_route_table_association.private
  ]

  tags = { Name = "${local.eks_cluster_name}-workers" }
}
