#!/usr/bin/env node
import "source-map-support/register";
import * as cdk from "aws-cdk-lib";
import { BedrockBrowserAgentStack } from "./lib/bedrock-browser-agent-stack";

const app = new cdk.App();

// Default environment - can be overridden via CDK context
const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION || "us-east-1",
};

new BedrockBrowserAgentStack(app, "BedrockBrowserAgentStack", {
  env,
  description: "AWS Bedrock Browser Agent - AI-powered attack surface management"
});
