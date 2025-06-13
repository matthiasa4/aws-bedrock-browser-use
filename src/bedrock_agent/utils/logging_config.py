"""Logging configuration for AWS Bedrock Browser Agent.

This module sets up unified logging for both Strands Agents SDK and application logging
with timestamped file outputs in a single log file.
"""

import logging
from datetime import datetime
from pathlib import Path


def setup_logging(logs_dir: str = "./logs"):
    """Set up unified logging configuration for all loggers.

    Args:
        logs_dir: Directory to store log files (default: "./logs")
    """
    # Create logs directory if it doesn't exist
    logs_path = Path(logs_dir)
    logs_path.mkdir(exist_ok=True)

    # Generate timestamp for log filenames
    timestamp = datetime.now().strftime("%Y-%m-%d-%H:%M:%S")

    # Create single log file for all logs
    log_file = logs_path / f"logs_{timestamp}.log"
    
    # Create formatters
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_formatter = logging.Formatter("%(levelname)s | %(name)s | %(message)s")

    # Configure the root logger (this will handle all loggers)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Clear any existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Create and add file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Create and add console handler (INFO level only)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # Configure specific loggers to reduce noise from AWS libraries
    aws_loggers = [
        "asyncioboto3",
        "botocore",
        "botocore.credentials", 
        "botocore.utils",
        "botocore.hooks",
        "botocore.loaders",
        "botocore.parsers",
        "botocore.endpoint",
        "botocore.auth",
        "strands.tools.mcp.mcp_client",
        "strands.tools.registry",
        "urllib3.connectionpool",
        "urllib3.util.retry",
    ]

    for logger_name in aws_loggers:
        aws_logger = logging.getLogger(logger_name)
        aws_logger.setLevel(logging.WARNING)  # Only show warnings and errors

    # Log configuration completion
    logger = logging.getLogger(__name__)
    logger.info("Unified logging configured - File: %s", log_file)

    return {
        "log_file": str(log_file),
        "logs_dir": str(logs_path),
    }


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
