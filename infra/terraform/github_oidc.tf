# Task 14: Trust only the exact GitHub repository and the main branch.
# Immutable subject uses permanent GitHub owner/repository IDs.
locals {
  github_oidc_url = "https://token.actions.githubusercontent.com"
  github_oidc_subject = "repo:balasekhardevops-coder@277724570/cloud-incident-prediction@1412641365:ref:refs/heads/main"
  github_deploy_role_name = "${var.project_name}-${var.environment}-github-deploy"
}

resource "aws_iam_openid_connect_provider" "github" {
  url             = local.github_oidc_url
  client_id_list  = ["sts.amazonaws.com"]
  # AWS IAM fetches and validates GitHub's TLS certificate itself.
  tags = { Purpose = "github-actions-oidc" }
}

data "aws_iam_policy_document" "github_oidc_trust" {
  statement {
    sid     = "OnlyMainOfThisRepository"
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = [local.github_oidc_subject]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  name                 = local.github_deploy_role_name
  assume_role_policy   = data.aws_iam_policy_document.github_oidc_trust.json
  max_session_duration = 3600
  tags = { Purpose = "mlops-deployment" }
}

# Permissions for the future ECR push workflow. Explicitly scoped to our ECR repository.
data "aws_iam_policy_document" "github_deploy" {
  statement {
    sid       = "ECRAuthorization"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    sid    = "PushAndInspectOneRepository"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability", "ecr:CompleteLayerUpload",
      "ecr:InitiateLayerUpload", "ecr:PutImage", "ecr:UploadLayerPart",
      "ecr:BatchGetImage", "ecr:DescribeImages", "ecr:DescribeRepositories"
    ]
    resources = [aws_ecr_repository.inference.arn]
  }
  statement {
    sid       = "DescribeTargetCluster"
    effect    = "Allow"
    actions   = ["eks:DescribeCluster"]
    resources = [aws_eks_cluster.mlops.arn]
  }
}

resource "aws_iam_role_policy" "github_deploy" {
  name   = "${var.project_name}-${var.environment}-deploy-access"
  role   = aws_iam_role.github_deploy.id
  policy = data.aws_iam_policy_document.github_deploy.json
}

# This is Kubernetes API authorization, distinct from the IAM policy above.
# The namespace must be created by a cluster administrator first.
resource "aws_eks_access_entry" "github_deploy" {
  cluster_name  = aws_eks_cluster.mlops.name
  principal_arn = aws_iam_role.github_deploy.arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "github_deploy" {
  cluster_name  = aws_eks_cluster.mlops.name
  principal_arn = aws_iam_role.github_deploy.arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSEditPolicy"
  access_scope {
    type       = "namespace"
    namespaces = ["incident-prediction"]
  }
  depends_on = [aws_eks_access_entry.github_deploy]
}

output "github_deploy_role_arn" {
  description = "IAM role ARN for the GitHub Actions OIDC workflow"
  value       = aws_iam_role.github_deploy.arn
}
