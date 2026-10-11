#!/usr/bin/env bash
# One-time bootstrap for a dedicated Terraform S3 state bucket.
# Requires AWS CLI v2, an authenticated AWS profile, and S3 permissions.
# Execute from any directory: bash infra/terraform/scripts/bootstrap_state.sh
set -euo pipefail

command -v aws >/dev/null || { echo "AWS CLI is required" >&2; exit 1; }
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-ap-south-1}}"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="${STATE_BUCKET:-cloud-incident-prediction-tfstate-${ACCOUNT_ID}-${REGION}}"
TF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

printf 'AWS account: %s\nRegion: %s\nTerraform state bucket: %s\n' "$ACCOUNT_ID" "$REGION" "$BUCKET"
if aws s3api head-bucket --bucket "$BUCKET" --expected-bucket-owner "$ACCOUNT_ID" 2>/dev/null; then
  echo 'Reusing existing, accessible, account-owned bucket.'
else
  echo 'Creating a NEW dedicated state bucket...'
  if [[ "$REGION" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION"
  else
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" \
      --create-bucket-configuration "LocationConstraint=$REGION"
  fi
fi

# Secure the bucket whether newly created or previously owned.
aws s3api put-public-access-block --bucket "$BUCKET" --expected-bucket-owner "$ACCOUNT_ID" \
  --public-access-block-configuration 'BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true'
aws s3api put-bucket-versioning --bucket "$BUCKET" --expected-bucket-owner "$ACCOUNT_ID" \
  --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption --bucket "$BUCKET" --expected-bucket-owner "$ACCOUNT_ID" \
  --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

# Enforce HTTPS-only access (TLS). Beware: this PUT overwrites an existing bucket policy.
# For safety, only write the policy to a newly created bucket; preserve existing policies.
# Existing bucket owners should review its policy manually to avoid replacing custom rules.
if [[ "${BOOTSTRAP_SET_TLS_POLICY:-yes}" == "yes" ]]; then
  if [[ "${BOOTSTRAP_REUSE_EXISTING:-no}" == "yes" ]]; then
    echo 'Skipping TLS policy change for explicitly reused bucket.'
  else
    # Refuse to replace any existing policy. Creating a new bucket has no policy.
    if aws s3api get-bucket-policy --bucket "$BUCKET" --expected-bucket-owner "$ACCOUNT_ID" >/dev/null 2>&1; then
      echo 'Existing bucket policy detected: not overwriting; verify it requires TLS.'
    else
      POLICY_FILE="$(mktemp)"
      trap 'rm -f "$POLICY_FILE"' EXIT
      cat > "$POLICY_FILE" <<EOF
{"Version":"2012-10-17","Statement":[{"Sid":"DenyNonTLS","Effect":"Deny","Principal":"*","Action":"s3:*","Resource":["arn:aws:s3:::$BUCKET","arn:aws:s3:::$BUCKET/*"],"Condition":{"Bool":{"aws:SecureTransport":"false"}}}]}
EOF
      aws s3api put-bucket-policy --bucket "$BUCKET" --expected-bucket-owner "$ACCOUNT_ID" --policy "file://$POLICY_FILE"
    fi
  fi
fi

BACKEND_CONFIG="$TF_DIR/backend.hcl"
if [[ -e "$BACKEND_CONFIG" ]]; then
  echo "Preserving existing $BACKEND_CONFIG. Confirm its bucket/key/region manually."
else
  cat > "$BACKEND_CONFIG" <<EOF
bucket = "$BUCKET"
key    = "cloud-incident-prediction/dev/terraform.tfstate"
region = "$REGION"
EOF
  echo "Wrote $BACKEND_CONFIG (excluded from Git)."
fi

echo 'Bootstrap complete. In infra/terraform run: terraform init -migrate-state -backend-config=backend.hcl'
