provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "cloud-incident-prediction"
      Environment = "bootstrap"
      ManagedBy   = "Terraform"
    }
  }
}

data "aws_caller_identity" "current" {}
