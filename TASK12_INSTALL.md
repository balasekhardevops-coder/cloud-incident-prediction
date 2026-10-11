> **State backend correction (2026-10-10):** Before running `terraform init` or `terraform apply`, complete `infra/terraform/BACKEND_SETUP.md` to bootstrap the dedicated state bucket and migrate any existing local state. Terraform >= 1.10 is required.

# Add Task 12 files to your existing clone

Extract this ZIP into the **repository root** of
`balasekhardevops-coder/cloud-incident-prediction`, preserving directories.
It adds `infra/terraform/` and `docs/project-checklist.md`; existing root
files and GitHub workflows are untouched.

Read `infra/terraform/README.md` and edit `terraform.tfvars` (copied from
`terraform.tfvars.example`) before planning or applying.

Git commands after review:

```bash
git switch -c feat/task-12-s3-ecr-terraform
git add infra/terraform docs/project-checklist.md
git status --short
git commit -m "infra: add Terraform S3 and ECR for MLOps"
git push -u origin feat/task-12-s3-ecr-terraform
```

If a branch with that name already exists, switch to it rather than recreating.
Push and open a pull request after locally validating Terraform.
