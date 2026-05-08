#!/usr/bin/env bash
# Deploys the data_explorer Streamlit app to AWS ECS Fargate.
# Prerequisites: aws CLI configured, Docker running, ANTHROPIC_API_KEY set.
set -euo pipefail

# ── Config ─────────────────────────────────────────────────────────────────────
AWS_REGION="${AWS_REGION:-us-east-1}"
APP_NAME="data-explorer"
CLUSTER_NAME="$APP_NAME"

# ── Resolve account ────────────────────────────────────────────────────────────
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REGISTRY="$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
IMAGE_URI="$ECR_REGISTRY/$APP_NAME:latest"

echo "==> Deploying $APP_NAME to AWS ECS Fargate ($AWS_REGION)"

# ── 1. ECR repository ──────────────────────────────────────────────────────────
echo "[1/7] Ensuring ECR repository..."
aws ecr describe-repositories --repository-names "$APP_NAME" \
    --region "$AWS_REGION" &>/dev/null || \
aws ecr create-repository --repository-name "$APP_NAME" \
    --region "$AWS_REGION" \
    --image-scanning-configuration scanOnPush=true \
    --output none

# ── 2. Build & push image ──────────────────────────────────────────────────────
echo "[2/7] Building and pushing Docker image..."
aws ecr get-login-password --region "$AWS_REGION" | \
    docker login --username AWS --password-stdin "$ECR_REGISTRY"
docker build -t "$APP_NAME:latest" .
docker tag "$APP_NAME:latest" "$IMAGE_URI"
docker push "$IMAGE_URI"

# ── 3. IAM task execution role ─────────────────────────────────────────────────
echo "[3/7] Ensuring ECS task execution role..."
ROLE_NAME="ecsTaskExecutionRole"
if ! EXEC_ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" \
        --query Role.Arn --output text 2>/dev/null); then
    EXEC_ROLE_ARN=$(aws iam create-role \
        --role-name "$ROLE_NAME" \
        --assume-role-policy-document '{
            "Version":"2012-10-17",
            "Statement":[{
                "Effect":"Allow",
                "Principal":{"Service":"ecs-tasks.amazonaws.com"},
                "Action":"sts:AssumeRole"
            }]
        }' \
        --query Role.Arn --output text)
    aws iam attach-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-arn "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
fi

# ── 4. CloudWatch log group ────────────────────────────────────────────────────
echo "[4/7] Ensuring CloudWatch log group..."
aws logs create-log-group --log-group-name "/ecs/$APP_NAME" \
    --region "$AWS_REGION" 2>/dev/null || true

# ── 5. ECS cluster ─────────────────────────────────────────────────────────────
echo "[5/7] Ensuring ECS cluster..."
aws ecs create-cluster --cluster-name "$CLUSTER_NAME" \
    --region "$AWS_REGION" --output none 2>/dev/null || true

# ── 6. Security group (allow :8501 inbound) ────────────────────────────────────
echo "[6/7] Ensuring security group..."
VPC_ID=$(aws ec2 describe-vpcs \
    --filters Name=isDefault,Values=true \
    --query "Vpcs[0].VpcId" --output text --region "$AWS_REGION")
SG_ID=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=$APP_NAME-sg" "Name=vpc-id,Values=$VPC_ID" \
    --query "SecurityGroups[0].GroupId" --output text \
    --region "$AWS_REGION" 2>/dev/null || echo "")
if [ -z "$SG_ID" ] || [ "$SG_ID" = "None" ]; then
    SG_ID=$(aws ec2 create-security-group \
        --group-name "$APP_NAME-sg" \
        --description "Streamlit port 8501" \
        --vpc-id "$VPC_ID" \
        --query GroupId --output text --region "$AWS_REGION")
    aws ec2 authorize-security-group-ingress \
        --group-id "$SG_ID" --protocol tcp --port 8501 --cidr "0.0.0.0/0" \
        --region "$AWS_REGION" --output none
fi
SUBNET_IDS=$(aws ec2 describe-subnets \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --query "Subnets[*].SubnetId" --output text \
    --region "$AWS_REGION" | tr '\t' ',')

# ── 7. Task definition & service ───────────────────────────────────────────────
echo "[7/7] Registering task definition and deploying service..."
: "${ANTHROPIC_API_KEY:?ANTHROPIC_API_KEY env var must be set}"

TASK_DEF_ARN=$(aws ecs register-task-definition \
    --family "$APP_NAME" \
    --network-mode awsvpc \
    --requires-compatibilities FARGATE \
    --cpu 1024 --memory 2048 \
    --execution-role-arn "$EXEC_ROLE_ARN" \
    --container-definitions "[{
        \"name\": \"$APP_NAME\",
        \"image\": \"$IMAGE_URI\",
        \"portMappings\": [{\"containerPort\": 8501, \"protocol\": \"tcp\"}],
        \"environment\": [{\"name\": \"ANTHROPIC_API_KEY\", \"value\": \"$ANTHROPIC_API_KEY\"}],
        \"logConfiguration\": {
            \"logDriver\": \"awslogs\",
            \"options\": {
                \"awslogs-group\": \"/ecs/$APP_NAME\",
                \"awslogs-region\": \"$AWS_REGION\",
                \"awslogs-stream-prefix\": \"ecs\"
            }
        }
    }]" \
    --region "$AWS_REGION" \
    --query "taskDefinition.taskDefinitionArn" --output text)

NET_CONFIG="awsvpcConfiguration={subnets=[$SUBNET_IDS],securityGroups=[$SG_ID],assignPublicIp=ENABLED}"

EXISTING_SERVICE=$(aws ecs describe-services \
    --cluster "$CLUSTER_NAME" --services "$APP_NAME" \
    --region "$AWS_REGION" \
    --query "services[?status!='INACTIVE'].serviceArn" --output text 2>/dev/null || true)

if [ -n "$EXISTING_SERVICE" ]; then
    aws ecs update-service \
        --cluster "$CLUSTER_NAME" --service "$APP_NAME" \
        --task-definition "$TASK_DEF_ARN" --force-new-deployment \
        --region "$AWS_REGION" --output none
    echo "Updated existing service — new task deploying."
else
    aws ecs create-service \
        --cluster "$CLUSTER_NAME" --service-name "$APP_NAME" \
        --task-definition "$TASK_DEF_ARN" \
        --desired-count 1 --launch-type FARGATE \
        --network-configuration "$NET_CONFIG" \
        --region "$AWS_REGION" --output none
    echo "Created new service — task starting (~60s)."
fi

# ── Resolve public IP ──────────────────────────────────────────────────────────
echo ""
echo "Waiting for task to reach RUNNING state..."
aws ecs wait services-stable \
    --cluster "$CLUSTER_NAME" --services "$APP_NAME" --region "$AWS_REGION"

TASK_ARN=$(aws ecs list-tasks \
    --cluster "$CLUSTER_NAME" --service-name "$APP_NAME" \
    --query "taskArns[0]" --output text --region "$AWS_REGION")
ENI_ID=$(aws ecs describe-tasks \
    --cluster "$CLUSTER_NAME" --tasks "$TASK_ARN" \
    --query "tasks[0].attachments[0].details[?name=='networkInterfaceId'].value" \
    --output text --region "$AWS_REGION")
PUBLIC_IP=$(aws ec2 describe-network-interfaces \
    --network-interface-ids "$ENI_ID" \
    --query "NetworkInterfaces[0].Association.PublicIp" \
    --output text --region "$AWS_REGION")

echo ""
echo "Your app is live at: http://$PUBLIC_IP:8501"
echo ""
echo "Note: the public IP changes on each deployment. For a stable URL, put an"
echo "      Application Load Balancer in front, or use a Cloudflare Tunnel."
