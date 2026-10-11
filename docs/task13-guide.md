> **State backend correction (2026-10-10):** Before running `terraform init` or `terraform apply`, complete `infra/terraform/BACKEND_SETUP.md` to bootstrap the dedicated state bucket and migrate any existing local state. Terraform >= 1.10 is required.

# Task 13 — VPC, EKS, IAM Terraform walkthrough

## Structure: new files only

```text
infra/terraform/
  vpc.tf                       # VPC, subnets, IGW, NAT, route tables
  iam.tf                       # Trust policies and EKS/node IAM roles
  eks.tf                       # EKS cluster and managed node group
  eks_variables.tf             # Task 13 input variables
  eks_outputs.tf               # Task 13 output values
  terraform.tfvars.task13.example # Values to APPEND to your existing terraform.tfvars
TASK13_INSTALL.md              # CLI steps
```

Task 12 files (`versions.tf`, `providers.tf`, `variables.tf`, `s3.tf`, `ecr.tf`, `outputs.tf`) remain in place. Terraform automatically loads all `*.tf` files in the same directory as **one root module**; the file names do not change their resource dependency behavior.

## `vpc.tf`

- `data.aws_availability_zones.available`: reads AZs available to the active AWS account; selects two.
- `aws_vpc.mlops`: provisions `10.20.0.0/16` by default; enables DNS support and DNS hostnames (required for EKS private API DNS).
- `aws_subnet.public`: public /24 subnets `10.20.0.0/24` and `10.20.1.0/24`; map public IP on launch; marked for future internet-facing load balancers.
- `aws_subnet.private`: private /24 subnets `10.20.10.0/24` and `10.20.11.0/24`; no automatic public IPs; marked for future internal load balancers.
- `aws_internet_gateway.mlops`: makes public Internet routes work for public IP-addressed resources.
- `aws_route_table.public` + `aws_route.public_internet`: 0.0.0.0/0 to IGW; associations attach this table to both public subnets.
- `aws_eip.nat` and `aws_nat_gateway.mlops`: one public NAT Gateway in public subnet A, with one Elastic IP.
- `aws_route_table.private` + `aws_route.private_egress`: 0.0.0.0/0 to NAT; associations attach this table to both private subnets.
- Each route table also receives the AWS-created `local` route for VPC CIDR; these don't need a separate Terraform `aws_route`.

**Why two AZs?** EKS cluster subnet configuration requires at least two AZs. Workers spread across private subnets. One NAT is a lab tradeoff: use NAT per AZ in production, plus separate route tables for AZ-local egress, or consider regional NAT if available and suitable.

## `iam.tf`

- `aws_iam_policy_document.eks_cluster_trust` grants `eks.amazonaws.com` the **ability to assume** the cluster role.
- `aws_iam_role.eks_cluster` receives `AmazonEKSClusterPolicy` so EKS control plane can manage required AWS resources.
- `aws_iam_policy_document.eks_nodes_trust` grants `ec2.amazonaws.com` assume-role trust for worker EC2 instances.
- `aws_iam_role.eks_nodes` receives `AmazonEKSWorkerNodePolicy` (node integration), `AmazonEC2ContainerRegistryPullOnly` (image pull), `AmazonEKS_CNI_Policy` (pod networking). For production, attach CNI permissions to its own pod/service-account identity with EKS Pod Identity/IRSA rather than every node.

**Trust policy vs permissions policy:** trust describes who *may assume* a role; attached permission policies describe what the role *may do*. These roles do not grant GitHub Actions the ability to deploy; GitHub OIDC is Task 14. Your Terraform identity must separately be permitted to create/pass these roles.

## `eks.tf`

- `aws_eks_cluster.mlops`: AWS manages the Kubernetes API/control plane; `subnet_ids` chooses both private subnets; `endpoint_private_access=true` allows VPC-local API requests; `endpoint_public_access=true` allows your laptop, but **only** from configured `eks_public_access_cidrs`.
- `access_config.authentication_mode="API_AND_CONFIG_MAP"` supports EKS access entries and legacy ConfigMap mode; `bootstrap_cluster_creator_admin_permissions=true` grants initial cluster admin to the IAM principal creating the cluster. Use an appropriate administrative role to apply.
- `aws_eks_node_group.mlops`: managed EC2 group in private subnets, on-demand t3.medium by default; desired 2, minimum 1, maximum 3; 30 GiB per node; AWS operates EC2 Auto Scaling.
- `depends_on` ensures IAM attachments and private NAT routing are created before node bootstrap.
- The cluster gets an EKS-managed cluster security group; this lab relies on AWS/EKS-managed defaults rather than opening custom ingress to worker nodes.

Node group `scaling_config` sets the initial/min/max *range*; it is not automatic CPU-based HPA. HPA/KEDA plus Cluster Autoscaler or Karpenter require additional components for pod/node autoscaling.

## `eks_variables.tf`

Defines `vpc_cidr`, `eks_kubernetes_version`, `eks_public_access_cidrs` (mandatory), `eks_node_instance_types`, `eks_node_desired_size`. The CIDR validation refuses a fully open `0.0.0.0/0` API endpoint.

## `eks_outputs.tf`

Exports VPC/subnet identifiers, EKS cluster name/endpoint, NAT public IP and IAM role ARNs. These become useful for verification and deployment workflows.

## Verification

```bash
aws sts get-caller-identity
terraform init
terraform fmt -recursive
terraform validate
terraform plan -out=tfplan
terraform show tfplan
terraform apply tfplan                 # only after review
terraform output
aws eks update-kubeconfig --region ap-south-1 --name cloud-incident-prediction-dev-eks
kubectl get nodes -o wide
kubectl get pods -n kube-system
```

Expected nodes: usually `Ready` once all EKS add-ons boot up. AWS `describe-cluster` status should be `ACTIVE` and managed node group should be `ACTIVE`. If nodes fail to join, review route table to NAT, node IAM policies, security groups, VPC DNS, and node group health issues.

## Not implemented yet

Task 14: GitHub OIDC role + trust policy. Task 15: build/push Docker image, manifests, image pull and external ingress/load balancer configuration. Task 16: validate service and rollback. These are separate from successful infrastructure creation.
