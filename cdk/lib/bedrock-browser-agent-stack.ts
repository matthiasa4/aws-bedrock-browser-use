import { Stack, StackProps, Duration, RemovalPolicy, CfnOutput } from "aws-cdk-lib";
import { Construct } from "constructs";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as ecs from "aws-cdk-lib/aws-ecs";
import * as iam from "aws-cdk-lib/aws-iam";
import * as logs from "aws-cdk-lib/aws-logs";
import * as elbv2 from "aws-cdk-lib/aws-elasticloadbalancingv2";
import * as secretsmanager from "aws-cdk-lib/aws-secretsmanager";

export class BedrockBrowserAgentStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    // Create a VPC for our Fargate service
    const vpc = new ec2.Vpc(this, "BedrockAgentVpc", {
      maxAzs: 2, // Use 2 Availability Zones for high availability
      natGateways: 1, // Use 1 NAT Gateway to reduce costs
      subnetConfiguration: [
        {
          cidrMask: 24,
          name: "Public",
          subnetType: ec2.SubnetType.PUBLIC,
        },
        {
          cidrMask: 24,
          name: "Private",
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
        },
      ],
    });

    // Create an ECS cluster
    const cluster = new ecs.Cluster(this, "BedrockAgentCluster", {
      vpc,
      clusterName: "bedrock-browser-agent-cluster",
      containerInsights: true,
    });

    // Create a log group for the container
    const logGroup = new logs.LogGroup(this, "BedrockAgentServiceLogs", {
      logGroupName: "/ecs/bedrock-browser-agent",
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: RemovalPolicy.DESTROY,
    });

    // Create secrets for sensitive environment variables
    const otlpHeadersSecret = new secretsmanager.Secret(this, "OTLPHeadersSecret", {
      secretName: "ecs/bedrock-browser-agent/OTEL_EXPORTER_OTLP_HEADERS",
      description: "Authorization header for LangFuse OTEL integration",
      generateSecretString: {
        secretStringTemplate: JSON.stringify({
          authorization: "Basic your-langfuse-credentials-here"
        }),
        generateStringKey: "authorization",
        excludeCharacters: " %+~`#$&*()|[]{}:;<>?!'/\"\\",
      },
    });

    // Create a task execution role
    const executionRole = new iam.Role(this, "BedrockAgentTaskExecutionRole", {
      assumedBy: new iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
      roleName: "bedrock-browser-agent-execution-role",
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName("service-role/AmazonECSTaskExecutionRolePolicy")
      ],
    });

    // Add permissions to read secrets
    executionRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ["secretsmanager:GetSecretValue"],
        resources: [otlpHeadersSecret.secretArn],
      })
    );

    // Create a task role with permissions to invoke Bedrock APIs
    const taskRole = new iam.Role(this, "BedrockAgentTaskRole", {
      assumedBy: new iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
      roleName: "bedrock-browser-agent-task-role",
    });

    // Add comprehensive permissions for the task to invoke Bedrock APIs
    taskRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
          "bedrock:GetFoundationModel",
          "bedrock:ListFoundationModels",
        ],
        resources: ["*"],
      })
    );

    // Add permissions for Bedrock Knowledge Base access
    taskRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "bedrock:Retrieve",
          "bedrock:RetrieveAndGenerate",
        ],
        resources: ["*"],
      })
    );

    // Create a task definition
    const taskDefinition = new ecs.FargateTaskDefinition(this, "BedrockAgentTaskDefinition", {
      family: "bedrock-browser-agent-task",
      memoryLimitMiB: 1024, // Increased for browser automation
      cpu: 512, // Increased for browser workload
      executionRole,
      taskRole,
      runtimePlatform: {
        cpuArchitecture: ecs.CpuArchitecture.X86_64, // Changed to x86_64 for better compatibility
        operatingSystemFamily: ecs.OperatingSystemFamily.LINUX,
      },
    });

    // Reference the existing ECR image built by deploy-to-ecr.sh
    const accountId = process.env.CDK_DEFAULT_ACCOUNT || this.account;
    const region = process.env.CDK_DEFAULT_REGION || this.region || "us-east-1";
    const repositoryName = "aws-bedrock-browser-agent";
    const imageTag = "latest";
    const ecrImageUri = `${accountId}.dkr.ecr.${region}.amazonaws.com/${repositoryName}:${imageTag}`;

    // Add container to the task definition
    const container = taskDefinition.addContainer("BedrockAgentContainer", {
      containerName: "bedrock-browser-agent",
      image: ecs.ContainerImage.fromRegistry(ecrImageUri),
      logging: ecs.LogDrivers.awsLogs({
        streamPrefix: "bedrock-agent",
        logGroup,
      }),
      environment: {
        // Application configuration
        NODE_ENV: "production",
        PORT: "8000",
        AWS_REGION: this.region,
        
        // Observability configuration
        OTEL_EXPORTER_OTLP_ENDPOINT: "https://cloud.langfuse.com/api/public/otel",
        
        // Bedrock configuration (can be overridden via context)
        BEDROCK_MODEL_ID: this.node.tryGetContext("bedrockModelId") || "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        BEDROCK_KNOWLEDGE_BASE_ID: this.node.tryGetContext("knowledgeBaseId") || "",
      },
      secrets: {
        OTEL_EXPORTER_OTLP_HEADERS: ecs.Secret.fromSecretsManager(otlpHeadersSecret, "authorization"),
      },
      portMappings: [
        {
          containerPort: 8000,
          protocol: ecs.Protocol.TCP,
          name: "http",
        },
      ],
      healthCheck: {
        command: ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        interval: Duration.seconds(30),
        timeout: Duration.seconds(5),
        retries: 3,
        startPeriod: Duration.seconds(60), // Give the app time to start
      },
    });

    // Create security group for the service
    const serviceSecurityGroup = new ec2.SecurityGroup(this, "BedrockAgentServiceSG", {
      vpc,
      description: "Security group for Bedrock Browser Agent Fargate Service",
      allowAllOutbound: true,
    });

    // Create a Fargate service
    const service = new ecs.FargateService(this, "BedrockAgentService", {
      cluster,
      taskDefinition,
      serviceName: "bedrock-browser-agent-service",
      desiredCount: 2, // Run 2 instances for high availability
      assignPublicIp: false, // Use private subnets with NAT gateway
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      securityGroups: [serviceSecurityGroup],
      circuitBreaker: {
        rollback: true,
      },
      minHealthyPercent: 50, // Allow rolling updates
      maxHealthyPercent: 200,
      healthCheckGracePeriod: Duration.seconds(120), // Give time for browser initialization
    });

    // Create security group for the Application Load Balancer
    const albSecurityGroup = new ec2.SecurityGroup(this, "BedrockAgentALBSG", {
      vpc,
      description: "Security group for Bedrock Browser Agent ALB",
      allowAllOutbound: true,
    });

    // Allow HTTP traffic from anywhere to the ALB
    albSecurityGroup.addIngressRule(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(80),
      "Allow HTTP traffic from anywhere"
    );

    // Allow HTTPS traffic from anywhere to the ALB (for future SSL setup)
    albSecurityGroup.addIngressRule(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(443),
      "Allow HTTPS traffic from anywhere"
    );

    // Allow ALB to reach the service
    serviceSecurityGroup.addIngressRule(
      albSecurityGroup,
      ec2.Port.tcp(8000),
      "Allow ALB to reach service"
    );

    // Create an Application Load Balancer
    const lb = new elbv2.ApplicationLoadBalancer(this, "BedrockAgentALB", {
      vpc,
      internetFacing: true,
      loadBalancerName: "bedrock-browser-agent-alb",
      securityGroup: albSecurityGroup,
    });

    // Create target group with health check configuration
    const targetGroup = new elbv2.ApplicationTargetGroup(this, "BedrockAgentTargets", {
      vpc,
      port: 8000,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targetType: elbv2.TargetType.IP,
      healthCheck: {
        enabled: true,
        path: "/health",
        port: "8000",
        protocol: elbv2.Protocol.HTTP,
        interval: Duration.seconds(30),
        timeout: Duration.seconds(5),
        healthyThresholdCount: 2,
        unhealthyThresholdCount: 5,
        healthyHttpCodes: "200",
      },
      deregistrationDelay: Duration.seconds(30),
      targets: [service],
    });

    // Create a listener for HTTP traffic
    const listener = lb.addListener("BedrockAgentListener", {
      port: 80,
      protocol: elbv2.ApplicationProtocol.HTTP,
      defaultAction: elbv2.ListenerAction.forward([targetGroup]),
    });

    // Add WebSocket support by configuring sticky sessions
    targetGroup.setAttribute("stickiness.enabled", "true");
    targetGroup.setAttribute("stickiness.type", "lb_cookie");
    targetGroup.setAttribute("stickiness.lb_cookie.duration_seconds", "86400");

    // Output the load balancer DNS name
    new CfnOutput(this, "BedrockAgentServiceEndpoint", {
      value: lb.loadBalancerDnsName,
      description: "The DNS name of the load balancer for the Bedrock Browser Agent Service",
    });

    // Output the service ARN
    new CfnOutput(this, "BedrockAgentServiceArn", {
      value: service.serviceArn,
      description: "The ARN of the ECS service",
    });

    // Output the cluster ARN
    new CfnOutput(this, "BedrockAgentClusterArn", {
      value: cluster.clusterArn,
      description: "The ARN of the ECS cluster",
    });

    // Output the secret ARN for manual configuration
    new CfnOutput(this, "OTLPHeadersSecretArn", {
      value: otlpHeadersSecret.secretArn,
      description: "ARN of the OTLP headers secret - configure this with your LangFuse credentials",
    });
  }
}
