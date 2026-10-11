# Task 13 additions. These extend the variables.tf from Task 12.
variable "vpc_cidr" {
  description = "IPv4 /16 network for the lab VPC; subnets are carved from it."
  type        = string
  default     = "10.20.0.0/16"

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr)) && can(regex("/16$", var.vpc_cidr))
    error_message = "Use an IPv4 /16 CIDR, such as 10.20.0.0/16."
  }
}

variable "eks_kubernetes_version" {
  description = "Supported Kubernetes minor version for Amazon EKS."
  type        = string
  default     = "1.36"
}

variable "eks_public_access_cidrs" {
  description = "Trusted public IPv4 CIDRs allowed to access the Kubernetes API (e.g. YOUR_PUBLIC_IP/32). Required: no default."
  type        = list(string)

  validation {
    condition = length(var.eks_public_access_cidrs) > 0 && alltrue([
      for cidr in var.eks_public_access_cidrs :
      can(cidrnetmask(cidr)) && cidr != "0.0.0.0/0"
    ])
    error_message = "Provide at least one valid IPv4 CIDR and do not use 0.0.0.0/0."
  }
}

variable "eks_node_instance_types" {
  description = "EC2 types for the EKS managed node group."
  type        = list(string)
  default     = ["t3.medium"]
}

variable "eks_node_desired_size" {
  description = "Initial EC2 node count across the two private subnets."
  type        = number
  default     = 2
  validation {
    condition     = var.eks_node_desired_size >= 1 && var.eks_node_desired_size <= 3
    error_message = "Choose a desired size from 1 to 3 for this lab."
  }
}
