terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
  # Intentionally no remote backend here at initial bootstrap.
  # Local state is used to create the main Terraform state bucket.
}
