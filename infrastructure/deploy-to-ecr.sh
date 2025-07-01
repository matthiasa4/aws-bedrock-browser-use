#!/bin/bash

# Deploy Docker image to Amazon ECR
# This script pushes your Docker image to ECR for App Runner deployment

set -e

# Configuration
REGION="us-east-1"  # Change this to your preferred region
REPOSITORY_NAME="aws-bedrock-browser-agent"
IMAGE_TAG="latest"

echo "🐳 Starting ECR deployment..."

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REPOSITORY_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPOSITORY_NAME"

echo "📋 Configuration:"
echo "   Account ID: $ACCOUNT_ID"
echo "   Region: $REGION"
echo "   Repository: $REPOSITORY_URI"

# Create ECR repository if it doesn't exist
echo "🏗️  Creating ECR repository..."
aws ecr describe-repositories --repository-names $REPOSITORY_NAME --region $REGION &> /dev/null || \
aws ecr create-repository \
    --repository-name $REPOSITORY_NAME \
    --region $REGION \
    --image-scanning-configuration scanOnPush=true

echo "✅ ECR repository ready"

# Get login token and login to ECR
echo "🔐 Logging into ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $REPOSITORY_URI

echo "🏗️  Building Docker image for amd64 platform..."
docker build --platform linux/amd64 -t $REPOSITORY_NAME .

echo "🏷️  Tagging image..."
docker tag $REPOSITORY_NAME:latest $REPOSITORY_URI:$IMAGE_TAG

echo "📤 Pushing image to ECR..."
docker push $REPOSITORY_URI:$IMAGE_TAG

echo ""
echo "✅ Docker image pushed successfully!"
echo "   Image URI: $REPOSITORY_URI:$IMAGE_TAG"
echo ""
echo "🚀 Ready for Fargate deployment!"
echo "   Run: ./infrastructure/deploy-to-fargate.sh"
