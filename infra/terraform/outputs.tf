output "artifact_bucket_name" {
  description = "Private S3 bucket for datasets and approved model artifacts."
  value       = aws_s3_bucket.artifacts.bucket
}

output "artifact_bucket_arn" {
  description = "S3 bucket ARN for future IAM policies."
  value       = aws_s3_bucket.artifacts.arn
}

output "ecr_repository_url" {
  description = "ECR Docker image repository URI for build and deploy workflows."
  value       = aws_ecr_repository.inference.repository_url
}

output "ecr_repository_arn" {
  description = "ECR repository ARN for IAM access controls."
  value       = aws_ecr_repository.inference.arn
}

output "aws_account_id" {
  description = "AWS account where resources were provisioned."
  value       = data.aws_caller_identity.current.account_id
}
