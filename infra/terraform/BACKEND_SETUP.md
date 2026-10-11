# Correction to Tasks 12–13 — Remote Terraform state (backend.tf)

The original Task 12–13 lab did not configure remote state. Add **backend.tf**
*before* continuing with Task 13. This is a bootstrap and state-migration step,
not an EKS resource. Do not manage the backend state bucket in this same Terraform root.

## Why two S3 buckets?

- **Terraform state S3 bucket**: Stores `cloud-incident-prediction/dev/terraform.tfstate`
  and temporary `terraform.tfstate.tflock` objects for concurrency locking.
- **Task 12 ML artifact S3 bucket**: Stores datasets and approved model files.
  Deleting/replacing artifact infrastructure must not make state unreachable.

The AWS provider and the S3 backend independently use the standard AWS credential
chain; e.g., `AWS_PROFILE=mlops-dev` and `aws sso login --profile mlops-dev`.
Neither needs static keys in HCL.

## 1. Prerequisites and identity

Install Terraform >= 1.10 (S3 native locking was introduced in 1.10) and AWS CLI v2.
In Git Bash:

```bash
export AWS_PROFILE=mlops-dev
aws sso login --profile mlops-dev
aws sts get-caller-identity
terraform version
```

Run in your intended **lab account**. Your AWS identity must have permission
to create/configure the backend bucket (or ask your AWS admin to pre-create it).

## 2. Bootstrap the state bucket outside Terraform root state

From the repository root:

```bash
export AWS_REGION=ap-south-1
bash infra/terraform/scripts/bootstrap_state.sh
```

The script calculates a globally unique state-bucket name using your AWS account
ID and Region. It creates the bucket if necessary; blocks all public access;
enables versioning and AES-256 (SSE-S3) at-rest encryption; adds a TLS-only
bucket policy unless one already exists; and writes `infra/terraform/backend.hcl`
with the literal bucket/key/region. The script does **not** run `terraform apply`.
Review any pre-existing bucket's bucket policy; the script preserves it.

S3 bucket creation and versions cost a small amount. AWS IAM controls who may
read/write your state. For the default workspace and configured key, grant:

- `s3:ListBucket` on the bucket (limited to the state key/prefix when practical)
- `s3:GetObject`, `s3:PutObject` on the state object
- `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` on `<state key>.tflock`

If you need to manually bootstrap instead, use AWS CLI/API to create a dedicated
bucket with the same protections, then copy `backend.hcl.example` to
`backend.hcl` and edit literal values.

## 3. Back up and migrate local state (if Task 12 already applied)

```bash
cd infra/terraform
# If local state exists, back it up outside the git repository:
mkdir -p "$HOME/terraform-state-backups"
if [[ -f terraform.tfstate ]]; then
  cp terraform.tfstate "$HOME/terraform-state-backups/cloud-incident-prediction-$(date +%Y%m%d-%H%M%S).tfstate"
fi

# IMPORTANT: This migrates existing state rather than ignoring it.
terraform init -migrate-state -backend-config=backend.hcl
```

Answer `yes` when Terraform asks to copy existing state. Do not use
`terraform init -reconfigure` when migrating an existing state — it skips state
migration. Don't delete a local backup until you have independently verified
remote state and secured any backups. If you have **no** existing state, the
same init command initializes an empty remote state backend.

## 4. Verify remote state, then plan

```bash
terraform state list
terraform fmt -check -recursive
terraform validate
terraform plan -out=tfplan
aws s3api get-bucket-versioning --bucket "$(awk -F" '/^bucket/{print $2}' backend.hcl)"
```

After an actual `terraform apply`, you can inspect the remote state object:

```bash
aws s3api head-object --bucket "$(awk -F" '/^bucket/{print $2}' backend.hcl)" \
  --key cloud-incident-prediction/dev/terraform.tfstate
```

`terraform state list` is empty on a new configuration until Terraform manages
resources. Avoid printing your entire state file (it can contain sensitive data).
The S3 `.tflock` object only exists temporarily while an operation holds a lock.

## 5. Important safety rules

- Do not commit `backend.hcl`, `.terraform/`, state, or saved plan files.
- Commit `backend.tf`, `backend.hcl.example`, and `.terraform.lock.hcl`.
- S3 backend configuration is evaluated **before** normal Terraform variables
  or provider blocks; it cannot use `var.aws_region`, `data.aws_caller_identity`,
  or resource attributes. This is why `backend.hcl` contains literal values.
- Do not create the state bucket as `aws_s3_bucket` in this same root module;
  instead keep it independent and protect it from accidental deletion.
- State locking via `use_lockfile = true` works with Terraform >= 1.10;
  DynamoDB-based state locking is deprecated.
- If AWS account/region/environment differs, change `backend.hcl` deliberately
  and migrate state rather than accidentally initializing a new empty state.
- Before enabling GitHub Actions in Task 14, use an OIDC-assumed IAM role with
  **least privilege for the state key and lockfile**, plus scoped infrastructure
  deployment permissions. Remote backend locking does not substitute for an
  approval gate or one-concurrent-apply workflow.

Official references:
- https://developer.hashicorp.com/terraform/language/backend/s3
- https://developer.hashicorp.com/terraform/cli/commands/init
- https://docs.aws.amazon.com/prescriptive-guidance/latest/terraform-aws-provider-best-practices/backend.html
