# Cloud Incident Prediction — 19-task implementation checklist

Updated: 2026-10-10. Tasks 1–11 were reported complete by the project owner.
Task 12 is implemented as a Terraform **starter package**, but is **not complete**
until AWS `terraform apply` and verification succeed.

## 1. Local ML development
- [x] 1. Set up VS Code and Python environment
- [x] 2. Generate simulated telemetry dataset
- [x] 3. Train and evaluate the classifier
- [x] 4. Inspect the training experiment in MLflow

## 2. Application development
- [x] 5. Run FastAPI prediction endpoint
- [x] 6. Execute automated tests
- [x] 7. Build and run Docker image

## 3. CI/CD
- [x] 8. Create GitHub repository
- [x] 9. Verify DevSecOps CI workflow
- [x] 10. Run continuous-training workflow
- [x] 11. Configure model release approval

## 4. AWS deployment
- [ ] 12. Provision S3 and ECR with Terraform — IN PROGRESS (code prepared; apply pending)
- [ ] 13. Add VPC, EKS and IAM infrastructure
- [ ] 14. Configure GitHub OIDC authentication
- [ ] 15. Deploy Docker image to EKS
- [ ] 16. Verify inference and rollback

## 5. Production improvements
- [ ] 17. Integrate real CloudWatch/Prometheus metrics
- [ ] 18. Register approved model versions in MLflow Registry
- [ ] 19. Implement monitoring, drift detection and retraining

## Task 12 completion criteria

1. Terraform initialized, formatted, and validated.
2. `terraform plan` reviewed with correct AWS account and Region.
3. `terraform apply` creates the S3 bucket, its controls, and ECR repository.
4. S3 public access block, versioning and encryption verified.
5. ECR repository and repository URL verified.
6. `.terraform.lock.hcl` committed; local state and credentials remain untracked.

**Current count: 11 of 19 complete; Task 12 in progress.**
