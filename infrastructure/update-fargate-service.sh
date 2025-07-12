#!/bin/bash

# Update ECS Fargate Service with Latest Image
# This script updates the existing ECS service with the newest image from ECR

set -e

# Configuration - Update these values to match deploy-to-fargate.sh
APP_NAME="bedrock-browser-agent"
ECR_REPOSITORY="010928204318.dkr.ecr.us-east-1.amazonaws.com/aws-bedrock-browser-agent"
IMAGE_TAG="latest"
AWS_REGION="us-east-1"
CONTAINER_PORT=8000

# Derived names (must match deploy-to-fargate.sh)
CLUSTER_NAME="${APP_NAME}-cluster"
SERVICE_NAME="${APP_NAME}-svc"
TASK_DEFINITION_NAME="${APP_NAME}-task"

echo "🔄 Updating ${APP_NAME} service with latest image..."

# Get or create execution role
echo "🔑 Getting IAM roles..."
EXECUTION_ROLE_ARN=$(aws iam get-role \
  --role-name ecsTaskExecutionRole \
  --query 'Role.Arn' \
  --output text 2>/dev/null || \
  echo "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/ecsTaskExecutionRole")

# Get task role ARN
TASK_ROLE_NAME="${APP_NAME}-task-role"
TASK_ROLE_ARN=$(aws iam get-role \
  --role-name $TASK_ROLE_NAME \
  --query 'Role.Arn' \
  --output text \
  --region $AWS_REGION 2>/dev/null || echo "")

if [ -z "$TASK_ROLE_ARN" ]; then
  echo "⚠️  Task role not found. Please run deploy-to-fargate.sh first to create the necessary IAM roles."
  exit 1
fi

# Ensure Secrets Manager permissions for execution role
echo "🔐 Ensuring Secrets Manager permissions for execution role..."
EXECUTION_POLICY_NAME="${APP_NAME}-execution-secrets-policy"
EXECUTION_POLICY_ARN="arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):policy/$EXECUTION_POLICY_NAME"

# Check if policy exists, if not, create it
aws iam get-policy --policy-arn "$EXECUTION_POLICY_ARN" >/dev/null 2>&1 || {
  echo "Creating execution secrets policy..."
  EXECUTION_POLICY_DOCUMENT=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:${AWS_REGION}:*:secret:ecs/${APP_NAME}/*"
    }
  ]
}
EOF
)
  aws iam create-policy \
    --policy-name $EXECUTION_POLICY_NAME \
    --policy-document "$EXECUTION_POLICY_DOCUMENT" \
    --region $AWS_REGION
}

# Attach execution policy to ecsTaskExecutionRole
aws iam attach-role-policy \
  --role-name ecsTaskExecutionRole \
  --policy-arn "$EXECUTION_POLICY_ARN" 2>/dev/null || echo "Execution policy already attached"

# Get current task definition to preserve settings
echo "📋 Getting current task definition..."
CURRENT_TASK_DEF=$(aws ecs describe-task-definition \
  --task-definition $TASK_DEFINITION_NAME \
  --region $AWS_REGION \
  --query 'taskDefinition')

# Extract current CPU and memory settings
CURRENT_CPU=$(echo $CURRENT_TASK_DEF | jq -r '.cpu // "256"')
CURRENT_MEMORY=$(echo $CURRENT_TASK_DEF | jq -r '.memory // "512"')

echo "💾 Current settings - CPU: ${CURRENT_CPU}, Memory: ${CURRENT_MEMORY}"

# Create new task definition with updated image
echo "📋 Creating new task definition with latest image..."
NEW_TASK_DEFINITION=$(cat <<EOF
{
  "family": "$TASK_DEFINITION_NAME",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "$CURRENT_CPU",
  "memory": "$CURRENT_MEMORY",
  "executionRoleArn": "$EXECUTION_ROLE_ARN",
  "taskRoleArn": "$TASK_ROLE_ARN",
  "containerDefinitions": [
    {
      "name": "$APP_NAME",
      "image": "$ECR_REPOSITORY:$IMAGE_TAG",
      "portMappings": [
        {
          "containerPort": $CONTAINER_PORT,
          "protocol": "tcp"
        }
      ],
      "essential": true,
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/$TASK_DEFINITION_NAME",
          "awslogs-region": "$AWS_REGION",
          "awslogs-stream-prefix": "ecs",
          "awslogs-create-group": "true"
        }
      },
      "environment": [
        {
          "name": "NODE_ENV",
          "value": "production"
        },
        {
          "name": "PORT",
          "value": "8000"
        },
        {
          "name": "AWS_REGION",
          "value": "$AWS_REGION"
        },
        {
          "name": "OTEL_EXPORTER_OTLP_ENDPOINT",
          "value": "https://cloud.langfuse.com/api/public/otel"
        }
      ],
      "secrets": [
        {
          "name": "OTEL_EXPORTER_OTLP_HEADERS",
          "valueFrom": "arn:aws:secretsmanager:$AWS_REGION:$(aws sts get-caller-identity --query Account --output text):secret:ecs/$APP_NAME/OTEL_EXPORTER_OTLP_HEADERS"
        }
      ]
    }
  ]
}
EOF
)

# Register new task definition
NEW_TASK_DEF_ARN=$(aws ecs register-task-definition \
  --cli-input-json "$NEW_TASK_DEFINITION" \
  --region $AWS_REGION \
  --query 'taskDefinition.taskDefinitionArn' \
  --output text)

echo "✅ New task definition registered: $NEW_TASK_DEF_ARN"

# Update the service with new task definition
echo "🚀 Updating ECS service..."
aws ecs update-service \
  --cluster $CLUSTER_NAME \
  --service $SERVICE_NAME \
  --task-definition $TASK_DEFINITION_NAME \
  --region $AWS_REGION

echo "⏳ Waiting for service to stabilize..."
aws ecs wait services-stable \
  --cluster $CLUSTER_NAME \
  --services $SERVICE_NAME \
  --region $AWS_REGION

# Get service status
echo "📊 Getting service status..."
SERVICE_STATUS=$(aws ecs describe-services \
  --cluster $CLUSTER_NAME \
  --services $SERVICE_NAME \
  --region $AWS_REGION \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,TaskDefinition:taskDefinition}')

echo "Service Status:"
echo $SERVICE_STATUS | jq '.'

# Get ALB endpoint
ALB_NAME="${APP_NAME}-alb"
ALB_DNS=$(aws elbv2 describe-load-balancers \
  --names $ALB_NAME \
  --query 'LoadBalancers[0].DNSName' \
  --output text \
  --region $AWS_REGION 2>/dev/null || echo "ALB not found")

echo ""
echo "✅ Service update completed successfully!"
echo ""
if [ "$ALB_DNS" != "ALB not found" ]; then
  echo "🌐 Your updated application is available at:"
  echo "   HTTP: http://$ALB_DNS"
  echo "   WebSocket: ws://$ALB_DNS"
else
  echo "⚠️  Could not retrieve ALB DNS name. Check AWS console for endpoint."
fi
echo ""
echo "🔄 To check deployment progress:"
echo "   aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $AWS_REGION"
echo ""
echo "📝 To view logs:"
echo "   aws logs tail /ecs/$TASK_DEFINITION_NAME --follow --region $AWS_REGION"
