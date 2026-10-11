# Task 15: Approved image -> ECR -> private EKS

## Prerequisites
- Task 14 OIDC trust and ECR push permissions successfully tested on GitHub Actions.
- A **successful**, independently approved `release.yaml` workflow run; note its run ID. Artifacts are retained 14 days.
- Existing ECR repository `cloud-incident-prediction-dev` and EKS cluster `cloud-incident-prediction-dev-eks` in `ap-south-1`.
- GitHub-to-AWS role has ECR push and EKS describe permissions; EKS nodes have ECR pull permissions.
- Your laptop's public IP is currently allowed in the EKS API public CIDRs. Do not broaden API access to `0.0.0.0/0`.

## How deployment works
1. Push these files to `main` through your regular review process.
2. GitHub Actions → **Build approved model image to ECR** → Run workflow, supply `release_run_id` from a successful `release.yaml` execution.
3. Workflow checks source release success, downloads *approved* model artifact and checks its SHA-256, builds the existing Dockerfile image (`src.api:app` port 8000), and pushes an immutable release tag to ECR.
4. Copy `IMAGE_URI=...` from the workflow summary.
5. Locally from repository root, run `IMAGE_URI='actual-ECR-URI' bash scripts/deploy-local.sh`.
6. Check service: `kubectl -n incident-prediction port-forward service/incident-api 8000:80`; in another terminal: `curl -fsS http://localhost:8000/health` and POST `/predict` with telemetry fields.

## Inference smoke test
```bash
curl -fsS -X POST http://localhost:8000/predict -H 'Content-Type: application/json' -d '{"cpu_usage_pct":85,"memory_usage_pct":90,"error_rate_pct":5.5,"p95_latency_ms":1800,"pod_restarts":3}'
```

## Rollback
```bash
kubectl -n incident-prediction rollout history deployment/incident-api
kubectl -n incident-prediction rollout undo deployment/incident-api
kubectl -n incident-prediction rollout status deployment/incident-api
```

## Design and limitations
- `ClusterIP` means the API is internal; testing uses `kubectl port-forward`. No publicly exposed load balancer is created.
- GitHub-hosted runners run outside your VPC; **this workflow only pushes to ECR**. `kubectl` runs from your allowed local IP instead. A future production pipeline should use a private connected runner (for example, inside the VPC) or GitOps controller.
- The workflow **requires** a successful approved release run. It does not promote a model solely because a file exists in Git.
- If using a different IAM role name, change `role-to-assume` to the actual Task 14 Terraform output.
- Verify with `kubectl -n incident-prediction get pods -o wide` and inspect `kubectl -n incident-prediction describe pod ...` if rollout fails.
- `readOnlyRootFilesystem` assumes application dependencies require no writeable paths after import. If startup logs show filesystem write errors, mount an `emptyDir` on the particular required location rather than disabling the security control broadly.
- This is a learning-lab deployment. Image digest pinning, automated release gating, admission controls, private build runners, metrics and alerting are future hardening steps.
