output "state_bucket_name" {
  value       = aws_s3_bucket.terraform_state.bucket
  description = "Use this bucket in the main configuration's backend.hcl"
}

output "backend_key" {
  value       = "cloud-incident-prediction/dev/terraform.tfstate"
  description = "State path for the main Terraform root"
}

output "aws_region" {
  value = var.aws_region
}
