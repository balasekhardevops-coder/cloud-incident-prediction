# Task 12: AWS S3 and ECR using Terraform

This directory provisions one private, versioned S3 bucket for ML data/model
artifacts and one private ECR repository for FastAPI/Docker images.

## Prerequisites

- Terraform >= 1.5; AWS CLI v2; Git; AWS permissions to create S3 and ECR resources.
- Prefer AWS IAM Identity Center (SSO) instead of long-lived access keys.
- Apply from VS Code's **Git Bash** terminal on Windows or a Unix shell.

## 1. Sign in to AWS (Git Bash)

```bash
aws configure sso --profile mlops-dev
aws sso login --profile mlops-dev
export AWS_PROFILE=mlops-dev
aws sts get-caller-identity
```

Check the account ID before continuing. Use a sandbox/lab account and an
identity with appropriate permissions. Do not put AWS credentials in Git.

## 2. Configure and preview

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars for the target Region and environment.
terraform version
terraform init
terraform fmt -recursive
terraform validate
terraform plan -out=tfplan
terraform show tfplan
```

`init` downloads the AWS provider and creates `.terraform.lock.hcl`, which is
safe and recommended to commit. The working files, state, tfvars and plan are
ignored by the local `.gitignore`. Review plan: it should show **six** resources
(4 S3 + 2 ECR) to add and no unexpected changes. If you modify inputs after
planning, run `terraform plan -out=tfplan` again.

## 3. Apply only after checking the account and plan

```bash
terraform apply tfplan
terraform output
```

This creates real AWS resources and may incur charges. No Terraform execution
has been performed automatically for this lab.

## 4. Validate in AWS

```bash
BUCKET=$(terraform output -raw artifact_bucket_name)
ECR_NAME=cloud-incident-prediction-dev
aws s3api head-bucket --bucket "$BUCKET"
aws s3api get-public-access-block --bucket "$BUCKET"
aws s3api get-bucket-versioning --bucket "$BUCKET"
aws s3api get-bucket-encryption --bucket "$BUCKET"
aws ecr describe-repositories --repository-names "$ECR_NAME" --region ap-south-1
terraform output -raw ecr_repository_url
```

Change `ECR_NAME` and `--region` to match terraform.tfvars if customized.
A successful `get-public-access-block` returns all four fields as true.
`get-bucket-versioning` should show `Enabled`.

## 5. Optional: test uploading a model artifact

From the repository root, assuming the model file exists:

```bash
aws s3 cp models/incident_model.joblib   "s3://$(cd infra/terraform && terraform output -raw artifact_bucket_name)/models/incident_model.joblib"
```

This file upload is optional and requires S3 PutObject permission.

## State and cost safety

- This introductory lab uses **local Terraform state**, not an S3 backend.
- Never commit or share `terraform.tfstate` or saved plan files; they can contain
  sensitive metadata. Back up state securely, avoid concurrent applies, and
  migrate to a separately bootstrapped remote backend before team/CI use.
- S3 versioning incurs storage charges for older versions. ECR images also cost
  storage; the lifecycle policy expires images beyond the latest 30.
- S3 bucket uses `force_destroy = false`; ECR uses `force_delete = false` to
  help prevent accidental deletion of stored artifacts/images.

## Cleanup (only after confirming data is no longer needed)

```bash
terraform plan -destroy
# Empty all versions of the S3 bucket and all ECR images first, if applicable.
terraform destroy
```

Be careful: `destroy` deletes real cloud resources and is not needed to complete
Task 12. Versioned buckets require deleting **all object versions and delete
markers**, not just current objects. Prefer retaining infrastructure for Task 13.
