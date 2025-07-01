#!/bin/bash

# ECS Fargate Deployment Script with WebSocket Support
# This script deploys a Docker container from ECR to ECS Fargate with ALB

set -e

# Configuration - Update these values
APP_NAME="aws-bedrock-agent"
ECR_REPOSITORY="010928204318.dkr.ecr.us-east-1.amazonaws.com/aws-bedrock-browser-agent"
IMAGE_TAG="latest"
AWS_REGION="us-east-1"
CONTAINER_PORT=8000
HEALTH_CHECK_PATH="/health"

# Derived names
CLUSTER_NAME="${APP_NAME}-cluster"
SERVICE_NAME="${APP_NAME}-svc"
TASK_DEFINITION_NAME="${APP_NAME}-task"
ALB_NAME="${APP_NAME}-alb"
TARGET_GROUP_NAME="${APP_NAME}-tg"
SECURITY_GROUP_NAME="${APP_NAME}-sg"

echo "🚀 Starting deployment of ${APP_NAME} to ECS Fargate..."

# Get default VPC and subnets
echo "📡 Getting VPC information..."
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=is-default,Values=true" --query "Vpcs[0].VpcId" --output text --region $AWS_REGION)
SUBNET_IDS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --query "Subnets[*].SubnetId" --output text --region $AWS_REGION)
SUBNET_ARRAY=($SUBNET_IDS)

echo "VPC ID: $VPC_ID"
echo "Subnets: ${SUBNET_ARRAY[@]}"

# Create security group for ALB
echo "🔒 Creating security group for ALB..."
ALB_SG_ID=$(aws ec2 create-security-group \
  --group-name "${ALB_NAME}-sg" \
  --description "Security group for ${APP_NAME} ALB" \
  --vpc-id $VPC_ID \
  --query 'GroupId' \
  --output text \
  --region $AWS_REGION 2>/dev/null || \
  aws ec2 describe-security-groups \
    --group-names "${ALB_NAME}-sg" \
    --query 'SecurityGroups[0].GroupId' \
    --output text \
    --region $AWS_REGION)

# Add ALB security group rules
aws ec2 authorize-security-group-ingress \
  --group-id $ALB_SG_ID \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0 \
  --region $AWS_REGION 2>/dev/null || echo "HTTP rule already exists"

aws ec2 authorize-security-group-ingress \
  --group-id $ALB_SG_ID \
  --protocol tcp \
  --port 443 \
  --cidr 0.0.0.0/0 \
  --region $AWS_REGION 2>/dev/null || echo "HTTPS rule already exists"

# Create security group for ECS tasks
echo "🔒 Creating security group for ECS tasks..."
ECS_SG_ID=$(aws ec2 create-security-group \
  --group-name "${SECURITY_GROUP_NAME}" \
  --description "Security group for ${APP_NAME} ECS tasks" \
  --vpc-id $VPC_ID \
  --query 'GroupId' \
  --output text \
  --region $AWS_REGION 2>/dev/null || \
  aws ec2 describe-security-groups \
    --group-names "${SECURITY_GROUP_NAME}" \
    --query 'SecurityGroups[0].GroupId' \
    --output text \
    --region $AWS_REGION)

# Allow ALB to reach ECS tasks
aws ec2 authorize-security-group-ingress \
  --group-id $ECS_SG_ID \
  --protocol tcp \
  --port $CONTAINER_PORT \
  --source-group $ALB_SG_ID \
  --region $AWS_REGION 2>/dev/null || echo "ECS ingress rule already exists"

# Create Application Load Balancer
echo "⚖️ Creating Application Load Balancer..."
ALB_ARN=$(aws elbv2 create-load-balancer \
  --name $ALB_NAME \
  --subnets ${SUBNET_ARRAY[@]} \
  --security-groups $ALB_SG_ID \
  --scheme internet-facing \
  --type application \
  --ip-address-type ipv4 \
  --query 'LoadBalancers[0].LoadBalancerArn' \
  --output text \
  --region $AWS_REGION 2>/dev/null || \
  aws elbv2 describe-load-balancers \
    --names $ALB_NAME \
    --query 'LoadBalancers[0].LoadBalancerArn' \
    --output text \
    --region $AWS_REGION)

# Create Target Group with WebSocket support
echo "🎯 Creating Target Group with WebSocket support..."
TG_ARN=$(aws elbv2 create-target-group \
  --name $TARGET_GROUP_NAME \
  --protocol HTTP \
  --protocol-version HTTP1 \
  --port $CONTAINER_PORT \
  --vpc-id $VPC_ID \
  --target-type ip \
  --health-check-enabled \
  --health-check-protocol HTTP \
  --health-check-path $HEALTH_CHECK_PATH \
  --health-check-interval-seconds 30 \
  --health-check-timeout-seconds 5 \
  --healthy-threshold-count 2 \
  --unhealthy-threshold-count 5 \
  --matcher HttpCode=200,101 \
  --query 'TargetGroups[0].TargetGroupArn' \
  --output text \
  --region $AWS_REGION 2>/dev/null || \
  aws elbv2 describe-target-groups \
    --names $TARGET_GROUP_NAME \
    --query 'TargetGroups[0].TargetGroupArn' \
    --output text \
    --region $AWS_REGION)

# Create ALB Listener
echo "👂 Creating ALB Listener..."
aws elbv2 create-listener \
  --load-balancer-arn $ALB_ARN \
  --protocol HTTP \
  --port 80 \
  --default-actions Type=forward,TargetGroupArn=$TG_ARN \
  --region $AWS_REGION 2>/dev/null || echo "Listener already exists"

# Create ECS Cluster
echo "🏗️ Creating ECS Cluster..."
aws ecs create-cluster \
  --cluster-name $CLUSTER_NAME \
  --capacity-providers FARGATE \
  --default-capacity-provider-strategy capacityProvider=FARGATE,weight=1 \
  --region $AWS_REGION 2>/dev/null || echo "Cluster already exists"

# Get or create execution role
echo "🔑 Setting up IAM roles..."
EXECUTION_ROLE_ARN=$(aws iam get-role \
  --role-name ecsTaskExecutionRole \
  --query 'Role.Arn' \
  --output text 2>/dev/null || \
  echo "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/ecsTaskExecutionRole")

# Create task role for AWS service access (Bedrock, etc.)
TASK_ROLE_NAME="${APP_NAME}-task-role"
echo "🔐 Creating/getting task role: $TASK_ROLE_NAME"

# Create task role if it doesn't exist
aws iam create-role \
  --role-name $TASK_ROLE_NAME \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Principal": {
          "Service": "ecs-tasks.amazonaws.com"
        },
        "Action": "sts:AssumeRole"
      }
    ]
  }' 2>/dev/null || echo "Task role already exists"

# Create custom policy for Bedrock access
POLICY_NAME="${APP_NAME}-bedrock-policy"
POLICY_DOCUMENT=$(cat infrastructure/bedrock-task-policy.json)

# Create policy if it doesn't exist
POLICY_ARN="arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):policy/$POLICY_NAME"
aws iam create-policy \
  --policy-name $POLICY_NAME \
  --policy-document "$POLICY_DOCUMENT" 2>/dev/null || echo "Policy already exists"

# Attach custom policy for Bedrock access
aws iam attach-role-policy \
  --role-name $TASK_ROLE_NAME \
  --policy-arn "$POLICY_ARN" 2>/dev/null || echo "Policy already attached"

# Get task role ARN
TASK_ROLE_ARN=$(aws iam get-role \
  --role-name $TASK_ROLE_NAME \
  --query 'Role.Arn' \
  --output text \
  --region $AWS_REGION)

# Add Secrets Manager permissions to execution role
echo "🔐 Adding Secrets Manager permissions to execution role..."
EXECUTION_POLICY_NAME="${APP_NAME}-execution-secrets-policy"
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

# Create execution policy if it doesn't exist
EXECUTION_POLICY_ARN="arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):policy/$EXECUTION_POLICY_NAME"
aws iam create-policy \
  --policy-name $EXECUTION_POLICY_NAME \
  --policy-document "$EXECUTION_POLICY_DOCUMENT" 2>/dev/null || echo "Execution policy already exists"

# Attach execution policy to ecsTaskExecutionRole
aws iam attach-role-policy \
  --role-name ecsTaskExecutionRole \
  --policy-arn "$EXECUTION_POLICY_ARN" 2>/dev/null || echo "Execution policy already attached"

# Create task definition
echo "📋 Creating ECS Task Definition..."
TASK_DEFINITION=$(cat <<EOF
{
  "family": "$TASK_DEFINITION_NAME",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
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
          "value": "https://us.cloud.langfuse.com/api/public/otel"
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

aws ecs register-task-definition \
  --cli-input-json "$TASK_DEFINITION" \
  --region $AWS_REGION

# Create ECS Service
echo "🚀 Creating ECS Service..."
aws ecs create-service \
  --cluster $CLUSTER_NAME \
  --service-name $SERVICE_NAME \
  --task-definition $TASK_DEFINITION_NAME \
  --desired-count 1 \
  --launch-type FARGATE \
  --platform-version LATEST \
  --network-configuration "awsvpcConfiguration={subnets=[${SUBNET_ARRAY[0]},${SUBNET_ARRAY[1]}],securityGroups=[$ECS_SG_ID],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=$TG_ARN,containerName=$APP_NAME,containerPort=$CONTAINER_PORT" \
  --region $AWS_REGION 2>/dev/null || echo "Service already exists, updating..."

# If service exists, update it
aws ecs update-service \
  --cluster $CLUSTER_NAME \
  --service $SERVICE_NAME \
  --task-definition $TASK_DEFINITION_NAME \
  --desired-count 1 \
  --region $AWS_REGION 2>/dev/null || echo "Service updated"

# Wait for service to be stable
echo "⏳ Waiting for service to stabilize..."
aws ecs wait services-stable \
  --cluster $CLUSTER_NAME \
  --services $SERVICE_NAME \
  --region $AWS_REGION

# Get ALB DNS name
ALB_DNS=$(aws elbv2 describe-load-balancers \
  --load-balancer-arns $ALB_ARN \
  --query 'LoadBalancers[0].DNSName' \
  --output text \
  --region $AWS_REGION)

echo "✅ Deployment completed successfully!"
echo ""
echo "🌐 Your application is available at:"
echo "   HTTP:  http://$ALB_DNS"
echo "   WebSocket: ws://$ALB_DNS (or wss:// if you set up SSL)"
echo ""
echo "📊 Resources created:"
echo "   Cluster: $CLUSTER_NAME"
echo "   Service: $SERVICE_NAME"
echo "   ALB: $ALB_NAME ($ALB_DNS)"
echo "   Target Group: $TARGET_GROUP_NAME"
echo "   Security Groups: $ALB_SG_ID, $ECS_SG_ID"
echo ""
echo "🔧 To clean up resources, run:"
echo "   aws ecs delete-service --cluster $CLUSTER_NAME --service $SERVICE_NAME --force --region $AWS_REGION"
echo "   aws ecs delete-cluster --cluster $CLUSTER_NAME --region $AWS_REGION"
echo "   aws elbv2 delete-load-balancer --load-balancer-arn $ALB_ARN --region $AWS_REGION"
echo "   aws elbv2 delete-target-group --target-group-arn $TG_ARN --region $AWS_REGION"