terraform {
  # S3-native state locking (use_lockfile) requires Terraform >= 1.10.
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}
