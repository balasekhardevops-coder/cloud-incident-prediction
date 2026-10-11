> **State backend correction (2026-10-10):** Before running `terraform init` or `terraform apply`, complete `infra/terraform/BACKEND_SETUP.md` to bootstrap the dedicated state bucket and migrate any existing local state. Terraform >= 1.10 is required.

# Task 13 install — add EKS to Task 12 Terraform

This is an **additive overlay** for `cloud-incident-prediction`. It is intended to be extracted into the same repository that already contains Task 12 at `infra/terraform/`. The archive does NOT replace your existing Task 12 `.tf` files or `terraform.tfvars`.

## Prerequisites
- Task 12 S3/ECR Terraform files already exist in `infra/terraform/`.
- You can authenticate to the correct AWS account using `aws sts get-caller-identity`.
- Terraform >= 1.10, `aws` CLI and `kubectl` available.
- IAM permission to create VPC, EC2 NAT/EIP, EKS, IAM roles/attachments and `iam:PassRole`.
- Budget controls: EKS, EC2, NAT, public IPv4 addresses and networking cost money until destroyed.

## Git Bash walkthrough

```bash
cd ~/cloud-incident-prediction/infra/terraform

# Find your laptop's CURRENT public IPv4. Don't copy the example TEST-NET IP.
curl -s https://checkip.amazonaws.com

# Open infra/terraform/terraform.tfvars in VS Code. APPEND the values
# from terraform.tfvars.task13.example and replace 203.0.113.10/32.
# Do not replace your existing aws_region/environment values.

aws sts get-caller-identity
terraform init -migrate-state -backend-config=backend.hcl
terraform fmt -recursive
terraform validate
terraform plan -out=tfplan
terraform show tfplan
```

Only after inspecting the planned changes:

```bash
terraform apply tfplan
terraform output
aws eks update-kubeconfig --region ap-south-1 --name cloud-incident-prediction-dev-eks
kubectl get nodes -o wide
kubectl get pods -n kube-system
aws eks describe-cluster --name cloud-incident-prediction-dev-eks --region ap-south-1 --query 'cluster.status'
aws eks describe-nodegroup --cluster-name cloud-incident-prediction-dev-eks --nodegroup-name cloud-incident-prediction-dev-workers --region ap-south-1 --query 'nodegroup.status'
```

Set the AWS region and profile according to your existing Task 12 settings. AWS CLI `update-kubeconfig` must authenticate as the identity that created the cluster (or one explicitly granted Kubernetes access). If your laptop public IP changes, update `eks_public_access_cidrs` and reapply from your trusted location before using `kubectl`.

## Route tracing

**Private worker -> public ECR endpoint:** private subnet route `0.0.0.0/0 -> NAT` -> public subnet route `0.0.0.0/0 -> Internet Gateway` -> ECR; reply traffic returns over established NAT connection.

**Worker -> Kubernetes API:** EKS private cluster endpoint through VPC-local routing (not NAT). VPC DNS and private endpoint enabled.

**Laptop -> Kubernetes API:** allowlisted laptop public IP -> EKS public API endpoint -> IAM authentication and Kubernetes authorization.

**Future external request -> FastAPI pod:** add a Kubernetes Service/Ingress and AWS Load Balancer Controller in later tasks. Nothing from the internet can reach the private pods yet.

## Costs and lifecycle
- Both private AZs share a single NAT in one AZ to limit costs; not HA, may incur cross-AZ data processing charges.
- EKS, EC2 nodes, NAT Gateway/EIP continue charging until removed; stop after lab.
- Terraform is one combined root module and one state, including S3/ECR from Task 12. `terraform destroy` destroys *both* Task 12 and Task 13 managed resources, not only EKS. Nonempty S3 buckets / ECR repositories can block deletion (deliberate safety guard).
- Keep `.tfstate`, `.tfvars` and saved `tfplan` out of Git; these may contain infrastructure details/secrets. Consider encrypted remote state with locking for team/production use.

See `docs/task13-guide.md` for detailed explanations.
