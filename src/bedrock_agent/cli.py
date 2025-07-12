"""AWS Bedrock Browser Agent - Main CLI Entry Point.

This module provides the command-line interface for the AWS Bedrock Browser Agent,
which performs automated attack surface management using browser automation and AI.
"""

import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path

from mcp import stdio_client

# Third-party imports
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from strands_tools import retrieve

# Local imports
from bedrock_agent.config.config import (
    get_filesystem_server_params,
    get_playwright_server_params,
)
from bedrock_agent.config.common_args import (
    add_browser_arguments,
    add_model_arguments,
    add_output_arguments,
    create_base_parser,
)
from bedrock_agent.utils.logging_callback_handler import create_logging_callback_handler
from bedrock_agent.utils.logging_config import get_logger, setup_logging
from bedrock_agent.utils.system_prompt import system_prompt

# Constants with environment variable support
DEFAULT_USER_INPUT = os.getenv(
    "DEFAULT_USER_INPUT",
    "Make your assessment of the website http://testphp.vulnweb.com",
)


def parse_arguments() -> argparse.Namespace:
    """Parse and validate command line arguments.

    Returns:
        Parsed arguments namespace

    Raises:
        SystemExit: If arguments are invalid
    """
    # Create parser with common formatting
    parser = create_base_parser("AWS Bedrock Browser Agent for Attack Surface Management")

    # Set examples in epilog
    parser.epilog = """
Examples:
  %(prog)s --input "Assess https://example.com"
  %(prog)s --headless --model anthropic.claude-v2
  %(prog)s --headless --log-level DEBUG
    """

    # Input options
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        help="Target URL or assessment instruction (skips interactive prompt)",
    )

    # Add common argument groups
    add_model_arguments(parser)  # Model options
    add_browser_arguments(parser)  # Browser options
    add_output_arguments(parser)  # Output options

    # Session options
    parser.add_argument(
        "--session-id",
        type=str,
        help="Custom session ID (auto-generated if not provided)",
    )

    return parser.parse_args()


def validate_arguments(args: argparse.Namespace) -> None:
    """Validate parsed arguments.

    Args:
        args: Parsed arguments to validate

    Raises:
        ValueError: If arguments are invalid
    """
    # Basic validation
    if not args.model:
        msg = "Model ID cannot be empty"
        raise ValueError(msg)

    # Create directories if they don't exist
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    
    if args.headless:
        print("Running in headless mode")


def get_user_input(args: argparse.Namespace) -> str:
    """Get assessment input from user or arguments.

    Args:
        args: Parsed command line arguments

    Returns:
        User input string
    """
    if args.input:
        user_input = args.input
        print(f"Using provided input: {user_input}")
    else:
        print("\n=== AWS Bedrock Browser Agent ===")
        print("Please enter the target URL or assessment instruction:")
        print("Example: 'Assess the security of https://example.com'")
        print("Example: 'https://testsite.com'")

        try:
            user_input = input("> ").strip()
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            sys.exit(0)

        if not user_input:
            print(f"No input provided, using default: {DEFAULT_USER_INPUT}")
            user_input = DEFAULT_USER_INPUT
            print("Using default assessment target")
        else:
            print(f"User provided input: {user_input}")

    return user_input


async def setup_mcp_clients(args: argparse.Namespace) -> tuple:
    """Set up MCP clients for browser and filesystem operations using Strands framework.

    Args:
        args: Parsed command line arguments

    Returns:
        Tuple of (playwright_client, filesystem_client)

    Raises:
        RuntimeError: If MCP client setup fails
    """
    try:
        # Get server parameters based on configuration
        playwright_params = get_playwright_server_params(
            headless=args.headless, use_docker=args.use_docker_mcps
        )
        filesystem_params = get_filesystem_server_params(use_docker=args.use_docker_mcps)

        print("Setting up MCP clients with Strands framework...")

        # Create MCP clients using Strands framework
        def create_playwright_transport():
            return stdio_client(playwright_params)

        def create_filesystem_transport():
            return stdio_client(filesystem_params)

        playwright_client = MCPClient(transport_callable=create_playwright_transport)
        filesystem_client = MCPClient(transport_callable=create_filesystem_transport)

        print("MCP clients initialized successfully")
        return playwright_client, filesystem_client

    except Exception as e:
        print(f"Failed to setup MCP clients: {e!s}")
        msg = f"MCP client initialization failed: {e!s}"
        raise RuntimeError(msg)


async def run_assessment(user_input: str, session_id: str, args: argparse.Namespace) -> None:
    """Run the security assessment using Strands Agents framework.

    Args:
        user_input: Assessment target/instruction
        session_id: Session identifier
        args: Command line arguments

    Raises:
        RuntimeError: If assessment fails
    """
    playwright_client = None
    filesystem_client = None

    try:
        # Setup MCP clients
        playwright_client, filesystem_client = await setup_mcp_clients(args)

        # Setup Bedrock model
        print(f"Initializing Bedrock model: {args.model}")
        bedrock_model = BedrockModel(model_id=args.model, streaming=False)

        # Start with built-in tools including knowledge base retrieval
        all_tools = [retrieve]

        # Use MCP clients in context managers to get tools
        with playwright_client, filesystem_client:
            # Get tools from both MCP servers
            playwright_tools = playwright_client.list_tools_sync()
            filesystem_tools = filesystem_client.list_tools_sync()

            # Combine all tools including retrieve
            all_tools.extend(playwright_tools + filesystem_tools)

            print(f"Loaded {len(all_tools)} tools (including knowledge base)")

            # Create logging callback handler
            logging_callback_handler = create_logging_callback_handler(
                "bedrock_agent.agent_callback"
            )

            # Create the main agent with all tools and callback handler
            agent = Agent(
                model=bedrock_model,
                system_prompt=system_prompt,
                tools=all_tools,
                callback_handler=logging_callback_handler,
            )

            print(f"Starting assessment with session ID: {session_id}")
            print(f"Using model: {args.model}")
            print(f"Knowledge base: {os.getenv('KNOWLEDGE_BASE_ID', 'Not configured')}")
            print(f"Target: {user_input}")

            # Run the assessment
            result = agent(user_input)

            # Print token usage and metrics
            print(f"Total tokens: {result.metrics.accumulated_usage['totalTokens']}")
            print(f"Input tokens: {result.metrics.accumulated_usage['inputTokens']}")
            print(f"Output tokens: {result.metrics.accumulated_usage['outputTokens']}")
            print(f"Execution time: {sum(result.metrics.cycle_durations):.2f} seconds")
            print(f"Tools used: {list(result.metrics.tool_metrics.keys())}")

            print("Assessment completed successfully")

    except Exception as e:
        print(f"Assessment failed: {e!s}")
        msg = f"Assessment failed: {e!s}"
        raise RuntimeError(msg)


async def main() -> None:
    """Main entry point for the AWS Bedrock Browser Agent.

    Raises:
        SystemExit: If critical errors occur
    """
    try:
        # Parse arguments
        args = parse_arguments()

        # Setup logging configuration
        log_config = setup_logging(logs_dir="./logs")
        logger = get_logger(__name__)

        print("AWS Bedrock Browser Agent starting...")
        logger.info("AWS Bedrock Browser Agent starting")
        logger.info("Logs: %s", log_config["log_file"])

        # Validate arguments
        validate_arguments(args)
        logger.info("Arguments validated successfully")

        # Generate session ID if not provided
        if not args.session_id:
            args.session_id = f"session-{uuid.uuid4()!s}"
        logger.info("Session ID: %s", args.session_id)

        # Get user input
        user_input = get_user_input(args)
        logger.info("User input: %s...", user_input[:100])  # Log first 100 chars

        # Run the assessment
        await run_assessment(user_input, args.session_id, args)

        print("Session completed successfully")
        print("\n✅ Assessment completed! Check the output directory for results.")
        logger.info("Session completed successfully")

    except ValueError as e:
        logger = get_logger(__name__)
        logger.exception("Configuration error: %s", e)
        print(f"❌ Configuration error: {e!s}")
        sys.exit(1)

    except RuntimeError as e:
        logger = get_logger(__name__)
        logger.exception("Runtime error: %s", e)
        print(f"❌ Runtime error: {e!s}")
        sys.exit(1)

    except KeyboardInterrupt:
        logger = get_logger(__name__)
        logger.info("Operation cancelled by user")
        print("\n⏹️  Operation cancelled by user.")
        sys.exit(0)

    except Exception as e:
        logger = get_logger(__name__)
        logger.error("Unexpected error: %s", e, exc_info=True)
        print(f"❌ Unexpected error: {e!s}")
        sys.exit(1)


def cli_main() -> None:
    """Entry point for the bedrock-browser-agent CLI command."""
    asyncio.run(main())


if __name__ == "__main__":
    cli_main()
