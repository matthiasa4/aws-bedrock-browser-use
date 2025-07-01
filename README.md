# AWS Bedrock Browser Agent - Enhanced with Strands Agents

[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![AWS Bedrock](https://img.shields.io/badge/AWS-Bedrock-orange.svg)](https://aws.amazon.com/bedrock/)
[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](pyproject.toml)

This project provides an AWS Bedrock-powered browser agent for automated attack surface management and security assessments.

## 🏗️ Architecture

The agent leverages the Strands framework with the following components:

### Core Components

- **Strands Agent**: Main orchestrator using Bedrock models
- **MCP Clients**:
  - Playwright MCP Server: Browser automation capabilities
  - Filesystem MCP Server: File operations and data management
- **Bedrock Model**: AWS Bedrock integration for LLM capabilities

### MCP Servers

The agent connects to two MCP servers:

1. **Playwright MCP Server**: Provides browser automation tools

   - Navigation, clicking, typing
   - Screenshot capture
   - Network monitoring
   - Console log access

2. **Filesystem MCP Server**: Provides file system operations
   - File reading/writing
   - Directory management
   - File system exploration

## 📋 Prerequisites

- Python 3.13+
- AWS Account with Bedrock access
- Docker (optional, for containerized deployment)
- Valid AWS credentials configured

## 🛠️ Installation

### Using pip

```bash
# Clone the repository
git clone https://github.com/matthiasa4/aws-bedrock-browser-agent.git
cd aws-bedrock-browser-agent

# Install the package in development mode
pip install -e .

# Install Playwright browsers
playwright install

# Install dependencies
pip install -r requirements.txt
```

After installation, the `bedrock-browser-agent` command will be available globally.

## ⚙️ Configuration

1. **AWS Configuration**: Ensure your AWS credentials are configured:

   ```bash
   aws configure
   ```

2. **Environment Variables**: Create a `.env` file based on `.env.example`:

   ```bash
   cp .env.example .env
   # Edit .env with your specific configuration
   ```

3. **Bedrock Access**: Ensure you have access to the required models:

   - `us.anthropic.claude-3-5-sonnet-20241022-v2:0`

4. **CVE Knowledge Base**: The agent uses a pre-processed CVE database for vulnerability analysis. The knowledge base data is included in the `data/knowledge-base/` directory, configured using `BEDROCK_KNOWLEDGE_BASE_ID` in your `.env` file.

## 🚀 Usage

### Command Line Interface

```bash
# Basic usage
python -m bedrock_agent.cli --input "Assess https://example.com"

# With specific model
python -m bedrock_agent.cli --model "us.anthropic.claude-3-5-sonnet-20241022-v2:0" --input "Your task"

# Headless mode
python -m bedrock_agent.cli --headless --input "Your task"

# Using Docker MCP servers
python -m bedrock_agent.cli --use-docker-mcps --input "Your task"
```

### Web Interface

```bash
# Start web server
python -m bedrock_agent.web

# With specific configuration
python -m bedrock_agent.web --headless --use-docker-mcps --port 8080

# Bind to specific host and port
python -m bedrock_agent.web --host 127.0.0.1 --port 9000

# With specific model
python -m bedrock_agent.web --model "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
```

Then navigate to `http://localhost:8000` (or your specified host:port).

### Docker

```bash
# Build the Docker image
docker build -t aws-bedrock-browser-agent .
```

```bash
# Using docker-compose
docker-compose up

# Or docker run directly
docker run -p 8000:8000 \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/logs:/app/logs \
  --env-file .env \
  --rm \
  --name aws-bedrock-browser-agent \
  aws-bedrock-browser-agent
```

## 📊 Output

The agent generates several types of output:

- **Security Findings**: JSON format with vulnerability details
- **Execution Logs**: Detailed trace of actions taken

Output files are saved to:

- `output/` - Current session results
- `logs/` - Execution logs and traces

## 🔧 Development

### Project Structure

```
aws-bedrock-browser-agent/
├── src/
│   └── bedrock_agent/          # Main package
│       ├── cli.py              # CLI interface
│       ├── web.py              # Web interface
│       ├── config/             # Configuration management
│       └── utils/              # Utility functions
├── infrastructure/             # Deployment scripts
├── data/                       # Static data and knowledge base
├── output/                     # Generated reports
├── logs/                       # Execution logs
├── pyproject.toml              # Project configuration
├── Dockerfile                  # Container definition
└── README.md                   # This file
```

## 🚢 Deployment

### AWS Fargate

Use the provided deployment scripts:

```bash
# Deploy to ECR
./infrastructure/deploy-to-ecr.sh

# Deploy to Fargate
./infrastructure/deploy-to-fargate.sh
```

### Environment Variables and Secrets Configuration

For Fargate deployments, the application supports both regular environment variables and secure secrets managed by AWS Secrets Manager.

#### Required Environment Variables

The following environment variables are automatically configured in the Fargate deployment:

- `NODE_ENV`: Set to "production"
- `PORT`: Application port (8000)
- `AWS_REGION`: AWS region for the deployment
- `OTEL_EXPORTER_OTLP_ENDPOINT`: OpenTelemetry endpoint for LangFuse integration

#### Setting up Secrets

To configure sensitive information like API keys or authentication headers, use AWS Secrets Manager:

1. **Create the OTEL_EXPORTER_OTLP_HEADERS secret** (required for LangFuse observability):

```bash
# Replace with your actual LangFuse authorization header
aws secretsmanager create-secret \
    --name "ecs/aws-bedrock-agent/OTEL_EXPORTER_OTLP_HEADERS" \
    --description "Authorization header for LangFuse OTEL integration" \
    --secret-string "Authorization=Basic your-langfuse-credentials-here" \
    --region us-east-1
```

#### Observability Configuration

The application is pre-configured to send observability data to LangFuse:

- **OTEL_EXPORTER_OTLP_ENDPOINT**: `https://cloud.langfuse.com/api/public/otel`
- **OTEL_EXPORTER_OTLP_HEADERS**: Retrieved securely from AWS Secrets Manager

Make sure to set up the `OTEL_EXPORTER_OTLP_HEADERS` secret with your LangFuse credentials before deploying.

### Configuration Options

The application supports extensive configuration via environment variables:

```bash
# AWS Configuration
AWS_REGION="us-east-1"
AWS_ACCESS_KEY_ID="your_access_key_here"
AWS_SECRET_ACCESS_KEY="your_secret_key_here"
AWS_SESSION_TOKEN="your_session_token_here_if_using_temporary_credentials"

# AWS Bedrock Configuration
BEDROCK_MODEL_ID="us.anthropic.claude-3-5-sonnet-20241022-v2:0"
BEDROCK_KNOWLEDGE_BASE_ID="cve-kb"

# Application Defaults (override CLI defaults)
DEFAULT_USER_INPUT="Make your assessment of the website http://testphp.vulnweb.com"
OUTPUT_DIR="./output"
```

### Command Line Options

```
--input, -i          Target URL or assessment instruction
--model, -m          AWS Bedrock model ID
--headless           Run browser in headless mode
--use-docker-mcps    Use Docker containers for MCP servers
--session-id         Custom session ID (auto-generated if not provided)
--output-dir         Output directory for results (default: ./output)
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Strands Agents](https://github.com/strands-agents/docs) - Modern AI agent framework
- [AWS Bedrock](https://aws.amazon.com/bedrock/) - Foundation model service
- [Playwright](https://playwright.dev/) - Browser automation framework
- [Model Context Protocol](https://github.com/modelcontextprotocol/mcp) - Tool integration standard
- [CVE Database](https://github.com/CVEProject/cvelistV5)
