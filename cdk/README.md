# AWS Bedrock Browser Agent - CDK Deployment

This directory contains the AWS CDK (Cloud Development Kit) infrastructure code for deploying the AWS Bedrock Browser Agent to AWS Fargate.

## Overview

The CDK stack creates:

- **VPC** with public and private subnets across 2 AZs
- **ECS Cluster** for running containerized workloads
- **Fargate Service** with 2 instances for high availability
- **Application Load Balancer** with health checks and WebSocket support
- **IAM Roles** with permissions for Bedrock API access
- **CloudWatch Logs** for monitoring and debugging
- **Secrets Manager** for secure credential storage
- **Security Groups** with appropriate network access rules

## Deployment Workflow

This CDK stack uses a two-step deployment process:

1. **Build and Push Docker Image** using the existing `deploy-to-ecr.sh` script
2. **Deploy Infrastructure** using CDK

This approach separates the container build process from the infrastructure deployment, giving you more control over each step.

## Prerequisites

1. **AWS CLI** configured with appropriate credentials
2. **Node.js** (version 18 or later)
3. **AWS CDK** installed globally: `npm install -g aws-cdk`
4. **Docker** for building and pushing the container image

## Setup

1. **Install dependencies:**

   ```bash
   cd cdk
   npm install
   ```

2. **Configure AWS credentials:**

   ```bash
   aws configure
   # or export AWS_PROFILE=your-profile
   ```

3. **Bootstrap CDK (first time only):**
   ```bash
   cdk bootstrap
   ```

## Deployment

### Step 1: Build and Push the Docker Image

First, build and push your Docker image to Amazon ECR using the existing script:

```bash
cd ..  # Go to project root
./infrastructure/deploy-to-ecr.sh
```

This script:
- Creates an ECR repository if it doesn't exist
- Builds the Docker image for amd64 platform
- Tags and pushes the image to ECR
- Uses "aws-bedrock-browser-agent:latest" as the repository and tag

### Step 2: Deploy the Infrastructure

After the image is pushed to ECR, deploy the CDK stack:

```bash
cd cdk
npm run build
cdk deploy
```

You can configure the deployment using CDK context:

```bash
# Set Bedrock model ID
cdk deploy -c bedrockModelId="us.anthropic.claude-3-5-sonnet-20241022-v2:0"

# Set Knowledge Base ID
cdk deploy -c knowledgeBaseId="your-knowledge-base-id"
```

### Check Deployment Status

```bash
# View stack outputs
cdk list
aws cloudformation describe-stacks --stack-name BedrockBrowserAgentStack
```

### Secrets Configuration

After deployment, configure the LangFuse observability secret:

```bash
# Get the secret ARN from CDK outputs
SECRET_ARN=$(aws cloudformation describe-stacks \
  --stack-name BedrockBrowserAgentStack \
  --query 'Stacks[0].Outputs[?OutputKey==`OTLPHeadersSecretArn`].OutputValue' \
  --output text)

# Update the secret with your LangFuse credentials
aws secretsmanager update-secret \
  --secret-id "$SECRET_ARN" \
  --secret-string "Authorization=Basic your-langfuse-credentials-here"
```

After updating the Secrets Manager secret, you need to force restart the containers to pick up the new secret values. Here are several ways to do this:

```bash
# Force new deployment of the service
aws ecs update-service \
  --cluster bedrock-browser-agent-cluster \
  --service bedrock-browser-agent-service \
  --force-new-deployment
```

Follow along with the logs:

```
aws logs tail /ecs/bedrock-browser-agent --follow
```

### Access the Application

After deployment, get the load balancer URL:

```bash
ALB_DNS=$(aws cloudformation describe-stacks \
  --stack-name BedrockBrowserAgentStack \
  --query 'Stacks[0].Outputs[?OutputKey==`BedrockAgentServiceEndpoint`].OutputValue' \
  --output text)

echo "Application URL: http://$ALB_DNS"
```

## Cleanup

To delete all resources:

```bash
cdk destroy
```

**Warning:** This will delete all resources including logs and data. Make sure to backup any important information first.
