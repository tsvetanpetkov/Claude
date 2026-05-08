#!/usr/bin/env bash
# Deploys the data_explorer Streamlit app to AWS App Runner via ECR.
# Prerequisites: aws CLI configured, Docker running, ANTHROPIC_API_KEY set.
set -euo pipefail

# ── Config ─────────────────────────────────────────────────────────────────────
AWS_REGION="${AWS_REGION:-us-east-1}"
APP_NAME="data-explorer"

# ── Resolve account ────────────────────────────────────────────────────────────
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REGISTRY="$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
IMAGE_URI="$ECR_REGISTRY/$APP_NAME:latest"

echo "==> Deploying $APP_NAME to AWS App Runner ($AWS_REGION)"

# ── 1. ECR repository ──────────────────────────────────────────────────────────
echo "[1/4] Ensuring ECR repository..."
aws ecr describe-repositories --repository-names "$APP_NAME" \
    --region "$AWS_REGION" &>/dev/null || \
aws ecr create-repository --repository-name "$APP_NAME" \
    --region "$AWS_REGION" \
    --image-scanning-configuration scanOnPush=true \
    --output none

# ── 2. Build & push image ──────────────────────────────────────────────────────
echo "[2/4] Building and pushing Docker image..."
aws ecr get-login-password --region "$AWS_REGION" | \
    docker login --username AWS --password-stdin "$ECR_REGISTRY"
docker build -t "$APP_NAME:latest" .
docker tag "$APP_NAME:latest" "$IMAGE_URI"
docker push "$IMAGE_URI"

# ── 3. IAM role for App Runner → ECR ──────────────────────────────────────────
echo "[3/4] Ensuring App Runner ECR access role..."
ROLE_NAME="AppRunnerECRAccessRole"
if ! ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" \
        --query Role.Arn --output text 2>/dev/null); then
    ROLE_ARN=$(aws iam create-role \
        --role-name "$ROLE_NAME" \
        --assume-role-policy-document '{
            "Version":"2012-10-17",
            "Statement":[{
                "Effect":"Allow",
                "Principal":{"Service":"build.apprunner.amazonaws.com"},
                "Action":"sts:AssumeRole"
            }]
        }' \
        --query Role.Arn --output text)
    aws iam attach-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-arn "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
fi

# ── 4. Create or update App Runner service ─────────────────────────────────────
echo "[4/4] Deploying App Runner service..."
: "${ANTHROPIC_API_KEY:?ANTHROPIC_API_KEY env var must be set}"

SOURCE_CONFIG=$(cat <<JSON
{
  "ImageRepository": {
    "ImageIdentifier": "$IMAGE_URI",
    "ImageConfiguration": {
      "Port": "8501",
      "RuntimeEnvironmentVariables": {
        "ANTHROPIC_API_KEY": "$ANTHROPIC_API_KEY"
      }
    },
    "ImageRepositoryType": "ECR"
  },
  "AutoDeploymentsEnabled": false,
  "AuthenticationConfiguration": {
    "AccessRoleArn": "$ROLE_ARN"
  }
}
JSON
)

EXISTING_ARN=$(aws apprunner list-services \
    --region "$AWS_REGION" \
    --query "ServiceSummaryList[?ServiceName=='$APP_NAME'].ServiceArn" \
    --output text)

if [ -n "$EXISTING_ARN" ]; then
    aws apprunner update-service \
        --service-arn "$EXISTING_ARN" \
        --source-configuration "$SOURCE_CONFIG" \
        --region "$AWS_REGION" \
        --output none
    echo "Updated existing service — deployment in progress."
else
    aws apprunner create-service \
        --service-name "$APP_NAME" \
        --source-configuration "$SOURCE_CONFIG" \
        --instance-configuration '{"Cpu":"1 vCPU","Memory":"2 GB"}' \
        --region "$AWS_REGION" \
        --output none
    echo "Created new service — deployment in progress (~2 min)."
fi

SERVICE_URL=$(aws apprunner list-services \
    --region "$AWS_REGION" \
    --query "ServiceSummaryList[?ServiceName=='$APP_NAME'].ServiceUrl" \
    --output text)

echo ""
echo "Your app will be live at: https://$SERVICE_URL"
echo "Track progress:           https://$AWS_REGION.console.aws.amazon.com/apprunner/home?region=$AWS_REGION#/services"
