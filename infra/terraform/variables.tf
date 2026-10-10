variable "aws_region" {
  description = "AWS Region for S3 and ECR."
  type        = string
  default     = "ap-south-1"
}

variable "project_name" {
  description = "Lowercase, DNS-safe project prefix (maximum 25 characters)."
  type        = string
  default     = "cloud-incident-prediction"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]*[a-z0-9]$", var.project_name)) && length(var.project_name) <= 25
    error_message = "Use 2-25 lowercase letters, digits or hyphens; begin with a letter and end with a letter or digit."
  }
}

variable "environment" {
  description = "Deployment environment, for example dev or prod."
  type        = string
  default     = "dev"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]*[a-z0-9]$", var.environment)) && length(var.environment) <= 8
    error_message = "Use 2-8 lowercase letters, digits or hyphens; begin with a letter and end with a letter or digit."
  }
}
