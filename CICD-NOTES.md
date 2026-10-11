# Cloud Incident Prediction — CI/CD & MLOps Notes

> Repository: `balasekhardevops-coder/cloud-incident-prediction`  
> AWS account: `758854589827` · Region: `ap-south-1`  
> Current deployment: EKS cluster `cloud-incident-prediction-dev-eks`, namespace `incident-prediction`, Deployment and Service `incident-api`.

## 1. Big picture

```text
Developer pushes to main
          |
          v
  ci.yaml (automatic)
  Unit tests + code quality + security gates
          |
          | A successful matching CI run is required for release approval.
          v
  train.yaml (manually started)
  Generate data -> preprocess -> train -> evaluate -> candidate artifact
          |
          | Training workflow run ID
          v
  release.yaml (manually started)
  Verify candidate and CI -> independent human approval -> approved artifact
          |
          | Release workflow run ID
          v
  build-approved-image.yml (manually started)
  Validate approved artifact -> OIDC -> build Docker -> push to Amazon ECR
          |
          | Exact ECR image URI
          v
  scripts/deploy-local.sh (manually run in local terminal)
  kubectl -> EKS Deployment -> ClusterIP Service -> FastAPI Pods
          |
          v
  Internal inference API: GET /health, POST /predict
```

**Important:** These arrows show dependencies, not automatic workflow chaining. Today, only CI automatically runs on a push to `main`. Training, approval, image publishing, and EKS deployment require explicit actions. The Docker image built inside CI is for testing; it is **not** the image pushed to ECR.

## 2. Existing workflows

| Workflow | Trigger | Main responsibility | Output |
|---|---|---|---|
| `.github/workflows/ci.yaml` | Push to `main`, pull request to `main`, manual | Unit tests, SonarQube, Semgrep, Snyk, container testing, OWASP ZAP, mandatory gate | Pass/fail and security results |
| `.github/workflows/train.yaml` | Manual (`workflow_dispatch`) | Generate synthetic telemetry, train/evaluate, log to MLflow, validate thresholds | Candidate model + manifest + training evidence |
| `.github/workflows/release.yaml` | Manual, requires training **run ID** | Verify training provenance, matching successful CI/security gate, checksum and metrics, independent approval | Approved model artifact and release manifest |
| `.github/workflows/build-approved-image.yml` | Manual, requires approved **release run ID** | Verify approval, stage exact model, assume AWS role via OIDC, build and push image | ECR image URI |

There is **no automated EKS deployment workflow** yet. We deliberately kept `release.yaml` unchanged rather than adding further permanent workflows.

## 3. CI — what happens on code push?

```bash
git add .
git commit -m "feat: update application"
git push origin main
```

CI runs several jobs:

1. **Quality:** `pytest` with 80% minimum coverage; SonarQube scan/quality gate for non-PR runs.
2. **SAST:** Semgrep checks code for security issues.
3. **SCA:** Snyk scans dependency vulnerabilities for non-PR runs.
4. **Docker/security:** Docker build, Snyk container scan (non-PR), FastAPI health and inference tests, OWASP ZAP baseline scan.
5. **Mandatory Security Gate:** Confirms required CI jobs succeeded (non-PR runs).

CI does **not** retrain models, publish a deployment image to ECR, or deploy to EKS.

## 4. Continuous training — how to train

### In GitHub Actions

Open: <https://github.com/balasekhardevops-coder/cloud-incident-prediction/actions/workflows/train.yaml>

Choose **Run workflow** on `main`.

`train.yaml` performs:

1. Install Python and dependencies.
2. `python data/generate_data.py` — reproducibly generate simulated CPU, memory, error-rate, latency, and restart data, with labels for incidents in the next 30 minutes.
3. `python src/train.py` — preprocess, split data chronologically, train Logistic Regression and Random Forest, evaluate, and select a winner.
4. Track experiments in MLflow (`sqlite:///mlflow.db` on the temporary runner).
5. Enforce candidate thresholds: validation **F1 >= 0.80** and **recall >= 0.80**.
6. Upload `incident-model-candidate-<TRAIN_RUN_ID>` containing `incident_model.joblib`, summary JSON, telemetry, and MLflow evidence.

**Record the training workflow run ID** (the number in `/actions/runs/<ID>`, not a job ID).

### Locally

```bash
cd ~/cloud-incident-prediction
python data/generate_data.py
# Ensure MLFLOW_TRACKING_URI points to a working MLflow backend.
python src/train.py
```

Local training alone does not register, approve, publish, or deploy the model.

## 5. Model approval — how to release a candidate

Open: <https://github.com/balasekhardevops-coder/cloud-incident-prediction/actions/workflows/release.yaml>

Choose **Run workflow** and enter the **successful training run ID**. The workflow:

- Confirms the candidate's source SHA passed the mandatory CI security gate.
- Validates the candidate manifest, metrics, source SHA, and SHA-256 artifact hashes.
- Requires **independent human approval** through the `model-release` GitHub Environment.
- Uploads `approved-incident-model-<RELEASE_RUN_ID>` and `release_manifest.json`.

**Record the release workflow run ID.** A successful release approval still does not deploy a model.

Previous example: training run `38045452711` → approved release run `38052793010`. These examples identify a completed historical release; for a new release, use its new run IDs.

## 6. Build and publish approved Docker image

Open: <https://github.com/balasekhardevops-coder/cloud-incident-prediction/actions/workflows/build-approved-image.yml>

Choose **Run workflow** and provide the **approved release run ID**, *not* the training run ID or job ID.

The workflow:

1. Fetches the successful release run metadata.
2. Downloads the approved model artifact and validates its approval manifest and checksum.
3. Copies the approved `incident_model.joblib` into the Docker build context.
4. Uses GitHub OIDC + AWS STS to assume `cloud-incident-prediction-dev-github-deploy` (no static AWS keys).
5. Builds with the repository `Dockerfile` and pushes to `cloud-incident-prediction-dev` in ECR.

Example approved image:

```text
758854589827.dkr.ecr.ap-south-1.amazonaws.com/cloud-incident-prediction-dev:release-38052793010-baae46647050ae5f4bbe804c6e0833c421d5d2f6
```

Use the **exact image URI** generated by the workflow for the release you are deploying. The tag's Git SHA is the image-build revision and need not equal the original training SHA.

## 7. Deploy the image to Amazon EKS

### Check AWS/Kubernetes access

```bash
aws sts get-caller-identity
aws eks update-kubeconfig --region ap-south-1 --name cloud-incident-prediction-dev-eks
kubectl get nodes -o wide
```

The cluster's public Kubernetes API endpoint is restricted by allowed IP CIDRs; if your public IP changes, update the trusted CIDR in Terraform and apply the reviewed plan. **Do not open it to `0.0.0.0/0`.**

### Deploy the exact ECR image

```bash
cd ~/cloud-incident-prediction
export IMAGE_URI="758854589827.dkr.ecr.ap-south-1.amazonaws.com/cloud-incident-prediction-dev:release-38052793010-baae46647050ae5f4bbe804c6e0833c421d5d2f6"
bash scripts/deploy-local.sh
```

The script updates kubeconfig, applies `k8s/namespace.yaml` and `k8s/service.yaml`, creates or updates the `incident-api` Deployment, and waits for rollout success.

Verify:

```bash
kubectl get deployments,pods,services -n incident-prediction -o wide
kubectl rollout status deployment/incident-api -n incident-prediction
kubectl get deployment incident-api -n incident-prediction \
  -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
```

Expected architecture: **two FastAPI replicas** on private EKS worker nodes, reachable internally through a **ClusterIP** Service.

## 8. Verify inference

In terminal 1:

```bash
kubectl port-forward -n incident-prediction service/incident-api 8050:80
```

In terminal 2:

```bash
curl -fsS http://localhost:8050/health
curl -fsS -X POST http://localhost:8050/predict \
  -H 'Content-Type: application/json' \
  -d '{
    "cpu_usage_pct": 85,
    "memory_usage_pct": 90,
    "error_rate_pct": 5.5,
    "p95_latency_ms": 1800,
    "pod_restarts": 3
  }'
```

The `/predict` response includes `prediction` (0/1), `incident_probability` (0–1), and `prediction_window_minutes` (30). Do not treat illustrative scores as actual model outputs.

**Ingress / AWS ALB has not been configured.** The app is currently reachable internally and through `kubectl port-forward`, not a public HTTPS inference URL.

## 9. Rollback and diagnostics

```bash
kubectl rollout history deployment/incident-api -n incident-prediction
kubectl rollout undo deployment/incident-api -n incident-prediction
kubectl rollout status deployment/incident-api -n incident-prediction --timeout=300s
kubectl logs -n incident-prediction deployment/incident-api --tail=100
kubectl describe pods -n incident-prediction
```

`rollout undo` requires a previous Deployment revision. Recheck `/health`, `/predict`, and the active image following rollback. Avoid using `undo` without a deliberate rollback reason in a live environment.

## 10. Frequent mistakes

| Symptom | Likely issue / fix |
|---|---|
| GitHub API 404 while validating a release run | Used a **job ID** instead of **workflow run ID**, or wrong run/repository |
| `Not authorized to perform sts:AssumeRoleWithWebIdentity` | OIDC trust mismatch or wrong IAM role ARN; match Terraform output |
| `NoSuchEntity` for deployment role | Workflow referenced `cloud-incident-prediction-github-deploy`; actual Terraform role is `cloud-incident-prediction-dev-github-deploy` |
| IAM OIDC Provider 409 already exists | Account-level GitHub OIDC provider already exists; reuse or carefully import rather than duplicating |
| `kubectl` times out to EKS API | Current client IP may no longer be in EKS public endpoint allowlist |
| API healthy but model output seems odd | Model is trained on **synthetic data**; performance on real incidents has not been established |

## 11. Current state and gaps

**Implemented and tested:** synthetic telemetry generation, preprocessing, scikit-learn training, MLflow experiment logging, CI/security gates, training candidate, independent model approval, OIDC authentication, ECR image publishing, Terraform EKS infrastructure, two-pod Deployment, service, health check, inference, and rollback rehearsal (per project execution).

**Deferred/skipped:** real CloudWatch/Prometheus telemetry integration (Task 17), persistent MLflow Model Registry (Task 18). Application monitoring, drift detection, and automated retraining (Task 19) are not implemented. There is no ALB Ingress/public endpoint or fully automated CD to EKS.

The present setup is a **working MLOps lab / delivery foundation**, not yet a production-validated incident prediction service. For production, retain independent approvals and security gates; consolidate publishing and EKS deployment into the existing release process with controlled VPC connectivity, immutable image digests, monitoring, and smoke tests.

## 12. Simple mental model

- **CI:** Is the code tested and secure?
- **Training:** Is there a good new model candidate?
- **Approval:** Is that precise model authorized for release?
- **Publishing:** Is the approved model packaged and stored as an ECR image?
- **Deployment:** Is that image running successfully on EKS?
- **Inference:** Can the serving API return predictions?

**In short:** `Code → CI` and `Data → Train → Approve → Build → ECR → EKS → Predict`.
