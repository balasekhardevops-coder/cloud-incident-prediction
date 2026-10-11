# Separate Terraform bootstrap — Cloud Incident Prediction

This ZIP is an add-on to the Task 12/13 Terraform repository, not a replacement for the existing Terraform root. Copy its `infra/bootstrap/` folder and the `infra/terraform/backend.tf` / `backend.hcl.example` files into your project, without overwriting customized files.

## Important: choose one bootstrap method

The previous Task 12/13 patch supplied `infra/terraform/scripts/bootstrap_state.sh`, which creates the **same named S3 bucket using the AWS CLI**. This new `infra/bootstrap` folder is an alternative that creates the bucket with **Terraform**. Do not run both creation methods for the same bucket.

If you **already ran** the AWS CLI bootstrap and the bucket exists, do **not** run `terraform apply` from `infra/bootstrap` until you import that bucket and its existing settings into this bootstrap configuration, or keep the CLI method instead.

## Fresh setup with Terraform bootstrap

These commands work in VS Code Git Bash, from the project root. Use an authenticated AWS profile:

```bash
export AWS_PROFILE=mlops-dev
aws sts get-caller-identity
cd infra/bootstrap
terraform init
terraform fmt -check
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
terraform output -raw state_bucket_name
```

Expected: an encrypted, private, versioned S3 bucket with TLS-only policy and protection against Terraform destroy. Terraform state in this bootstrap root is initially **local**. Securely back up `infra/bootstrap/terraform.tfstate` outside Git; do not delete it or commit it. For longer-term management, plan a controlled migration of the bootstrap state to durable restricted storage.

## Configure the main Terraform backend

Move from `infra/bootstrap` to `infra/terraform`, where Tasks 12 and 13 live:

```bash
cd ../terraform
STATE_BUCKET=$(terraform -chdir=../bootstrap output -raw state_bucket_name)
cat > backend.hcl <<EOF
bucket = "$STATE_BUCKET"
key    = "cloud-incident-prediction/dev/terraform.tfstate"
region = "ap-south-1"
EOF
```

If Task 12 has already been applied locally, back up `infra/terraform/terraform.tfstate` somewhere secure and run:

```bash
terraform init -migrate-state -backend-config=backend.hcl
```

If no previous Terraform initialization/state exists in this root, run:

```bash
terraform init -backend-config=backend.hcl
```

Then:

```bash
terraform state list
terraform plan
```

**Important:** Never place state files or access keys in Git. Only one backend declaration can be active in the `infra/terraform` root. If you already added `backend.tf` from the earlier patch, do not duplicate it. Change the backend `key` per environment (dev/stage/prod) and restrict IAM to the appropriate state paths.

HashiCorp docs: https://developer.hashicorp.com/terraform/language/backend/s3
