"""Common argument definitions for AWS Bedrock Browser Agent.

This module defines shared argument definitions that can be used across different
entry points (CLI, web server, etc.), ensuring consistent behavior.
"""

import argparse
import os


def add_browser_arguments(parser: argparse.ArgumentParser) -> None:
    """Add browser-related arguments to an ArgumentParser.

    Args:
        parser: The ArgumentParser to add arguments to
    """
    parser.add_argument(
        "--headless", action="store_true", help="Run browser in headless mode (no GUI)"
    )

    parser.add_argument(
        "--use-docker-mcps",
        action="store_true",
        help="Use Docker containers for MCP servers (always headless)",
    )


def add_model_arguments(parser: argparse.ArgumentParser) -> None:
    """Add model-related arguments to an ArgumentParser.

    Args:
        parser: The ArgumentParser to add arguments to
    """
    parser.add_argument(
        "--model",
        "-m",
        type=str,
        default=os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-3-5-sonnet-20241022-v2:0"),
        help="AWS Bedrock model ID to use",
    )


def add_output_arguments(parser: argparse.ArgumentParser) -> None:
    """Add output-related arguments to an ArgumentParser.

    Args:
        parser: The ArgumentParser to add arguments to
    """
    parser.add_argument(
        "--output-dir",
        type=str,
        default=os.getenv("OUTPUT_DIR", "./output"),
        help="Output directory for results (default: ./output)",
    )


def create_base_parser(description: str) -> argparse.ArgumentParser:
    """Create a base ArgumentParser with common help formatter.

    Args:
        description: Parser description

    Returns:
        ArgumentParser with raw text formatter
    """
    return argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawTextHelpFormatter,
    )
