#!/usr/bin/env bash
set -euo pipefail

# Run from the repository root after GitHub Actions pushes an approved release image.
# Example: IMAGE_URI=758854589827.dkr.ecr.ap-south-1.amazonaws.com/cloud-incident-prediction-dev:release-123456-abc123... bash scripts/deploy-local.sh
: "${IMAGE_URI:?Set IMAGE_URI to the exact ECR image URI printed by the release build workflow}"
[[ "$IMAGE_URI" == 758854589827.dkr.ecr.ap-south-1.amazonaws.com/cloud-incident-prediction-dev:release-* ]] || { echo "Unexpected IMAGE_URI" >&2; exit 1; }

aws eks update-kubeconfig --region ap-south-1 --name cloud-incident-prediction-dev-eks
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/service.yaml

if kubectl -n incident-prediction get deployment incident-api >/dev/null 2>&1; then
  kubectl -n incident-prediction set image deployment/incident-api "incident-api=${IMAGE_URI}"
else
  sed "s|REPLACE_IMAGE_URI|${IMAGE_URI}|" k8s/deployment.yaml | kubectl apply -f -
fi
kubectl -n incident-prediction rollout status deployment/incident-api --timeout=300s
kubectl -n incident-prediction get pods -o wide
kubectl -n incident-prediction get service incident-api
