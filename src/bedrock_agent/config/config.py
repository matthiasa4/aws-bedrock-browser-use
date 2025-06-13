import os
import glob

import boto3
from dotenv import load_dotenv
from mcp import StdioServerParameters

# Load environment variables first
load_dotenv()

# Create AWS session with proper region configuration
aws_session = boto3.Session(
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    aws_session_token=os.environ.get("AWS_SESSION_TOKEN"),
    region_name=os.environ.get("AWS_REGION", "us-east-1"),
)

# Get the directory where this file is located
current_dir = os.path.dirname(os.path.abspath(__file__))  # src/bedrock_agent/config/
# Go up to bedrock_agent, then src, then project root
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))

# Get output directory from environment variable or use default
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", os.path.join(project_root, "output/"))


def get_playwright_server_params(headless=False, use_docker=False):
    """Get Playwright server parameters based on configuration.

    Args:
        headless: Whether to run Playwright in headless mode
        use_docker: Whether to use Docker containers for MCP servers

    Returns:
        StdioServerParameters: The configured parameters
    """
    if use_docker:
        # Docker containers are always headless - no display options needed
        return StdioServerParameters(
            command="docker",
            args=[
                "run",
                "-i",
                "--rm",
                "--init",
                "--pull=always",
                "mcr.microsoft.com/playwright/mcp",
            ],
        )
    # Use binary/npm package - can be headed or headless
    npm_args = [
        "@playwright/mcp@latest",
        "--browser",
        "chromium",
        "--no-sandbox",
    ]

    if headless:
        npm_args.append("--headless")

    # Check if we're in a container environment and need to specify executable path
    if os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH"):
        # Use the environment variable set in Docker
        exec_path = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
        # Handle wildcard in path by finding the actual directory
        if "*" in exec_path:
            import glob

            matching_paths = glob.glob(exec_path)
            if matching_paths:
                exec_path = matching_paths[0]
        npm_args.extend(["--executable-path", exec_path])
    elif os.path.exists("/.dockerenv"):
        # Fallback for Docker environments without the env var
        # Try to find the Chromium executable in common Docker locations
        possible_paths = [
            "/root/.cache/ms-playwright/chromium-*/chrome-linux/chrome",
            "/ms-playwright/chromium-*/chrome-linux/chrome",
        ]
        import glob

        for path_pattern in possible_paths:
            matching_paths = glob.glob(path_pattern)
            if matching_paths:
                npm_args.extend(["--executable-path", matching_paths[0]])
                break

    # If not headless, run in headed mode (default for local development)

    return StdioServerParameters(
        command="npx",
        args=npm_args,
    )


def get_filesystem_server_params(use_docker=False):
    """Get filesystem server parameters based on configuration.

    Args:
        use_docker: Whether to use Docker containers for MCP servers

    Returns:
        StdioServerParameters: The configured parameters
    """
    if use_docker:
        # Use Docker container
        return StdioServerParameters(
            command="docker",
            args=[
                "run",
                "-i",
                "--rm",
                "--mount",
                f"type=bind,src={OUTPUT_DIR},dst=/projects/{OUTPUT_DIR}",
                "mcp/filesystem",
                "/projects",
            ],
        )
    # Use binary/npm package
    return StdioServerParameters(
        command="npx", args=["@modelcontextprotocol/server-filesystem", OUTPUT_DIR]
    )


# Default to the non-headless, non-docker version for easy local development
# These will be overridden by the CLI or web apps
playwright_server_params = get_playwright_server_params(headless=False, use_docker=False)
filesystem_server_params = get_filesystem_server_params(use_docker=False)

# Print configuration info for debugging
if __name__ == "__main__":
    # Simple defaults when run directly
    headless = False
    use_docker = False

    print("=== Browser Agent Configuration ===")
    print(f"Use Docker MCPs: {use_docker}")
    if use_docker:
        print("Playwright mode: Headless (Docker - always headless)")
    else:
        print(f"Playwright mode: {'Headless' if headless else 'Headed'} (Binary)")

    # Get parameters for the current configuration
    pw_params = get_playwright_server_params(headless=headless, use_docker=use_docker)
    fs_params = get_filesystem_server_params(use_docker=use_docker)

    print("\n=== Playwright Configuration ===")
    print(f"Command: {pw_params.command}")
    print(f"Args: {' '.join(pw_params.args)}")
    print("\n=== Filesystem Configuration ===")
    print(f"Command: {fs_params.command}")
    print(f"Args: {' '.join(fs_params.args)}")
