import argparse
import json
import os
import sys
import traceback

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from mcp import stdio_client
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from strands_tools import retrieve

from bedrock_agent.config.config import (
    filesystem_server_params,
    playwright_server_params,
)
from bedrock_agent.config.common_args import (
    add_browser_arguments,
    add_model_arguments,
    create_base_parser,
)
from bedrock_agent.utils.logging_config import get_logger, setup_logging
from bedrock_agent.utils.system_prompt import system_prompt

app = FastAPI()

# Global configuration (will be set by command line args)
global_args = None


def parse_web_args():
    """Parse command line arguments for web server interface."""
    # Create parser with common formatting
    parser = create_base_parser("AWS Bedrock Browser Agent Web Interface")

    # Add common argument groups
    add_browser_arguments(parser)  # Browser options
    add_model_arguments(parser)  # Model options

    # Web server specific arguments
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind the web server to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind the web server to (default: 8000)",
    )

    args = parser.parse_args()
    
    return args


# Store active connections for streaming output
class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.remove(websocket)

    async def send_message(self, message: str, message_type: str = "normal") -> None:
        # Send structured message with type information
        message_data = json.dumps({"text": message, "type": message_type})
        for connection in self.active_connections:
            try:
                await connection.send_text(message_data)
            except:
                # Connection might be closed, remove it
                if connection in self.active_connections:
                    self.active_connections.remove(connection)


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/health")
async def health_check():
    """Health check endpoint for ALB/ELB health checks."""
    return {"status": "healthy", "service": "aws-bedrock-browser-agent"}


@app.get("/")
async def get_frontend():
    # Get current configuration for display
    if global_args.use_docker_mcps:
        mode = "Local (Docker - Headless)"
    elif global_args.headless:
        mode = "Local (Headless)"
    else:
        mode = "Local (Headed)"

    return HTMLResponse(
        content=f"""
<!DOCTYPE html>
<html>
<head>
    <title>AWS Bedrock Browser Agent</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        h1 {{
            background: linear-gradient(90deg, #667eea, #764ba2);
            color: white;
            margin: 0;
            padding: 20px;
            text-align: center;
        }}
        .config-info {{
            background: #f8f9fa;
            padding: 10px 20px;
            border-bottom: 1px solid #dee2e6;
            font-size: 14px;
            color: #6c757d;
        }}
        .input-section {{
            padding: 20px;
            border-bottom: 1px solid #eee;
        }}
        input[type="text"] {{
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 5px;
            font-size: 16px;
            margin-bottom: 10px;
            box-sizing: border-box;
        }}
        input[type="text"]:focus {{
            border-color: #667eea;
            outline: none;
        }}
        button {{
            background: linear-gradient(90deg, #667eea, #764ba2);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            transition: transform 0.2s;
        }}
        button:hover {{
            transform: translateY(-2px);
        }}
        button:disabled {{
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }}
        .output-section {{
            height: 500px;
            overflow-y: auto;
            padding: 20px;
            background: #f8f9fa;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            line-height: 1.4;
        }}
        .output-line {{
            margin-bottom: 5px;
            padding: 2px 0;
        }}
        .output-line.thought {{
            color: #6f42c1;
            font-style: italic;
            background-color: rgba(111, 66, 193, 0.15);
            border-left: 4px solid #6f42c1;
            padding: 10px;
            margin: 6px 0;
            border-radius: 6px;
            box-shadow: 0 1px 3px rgba(111, 66, 193, 0.2);
            animation: fadeInThought 0.5s ease-in;
        }}
        .output-line.thought::before {{
            content: "🧠 ";
            font-style: normal;
            font-size: 1.1em;
        }}
        @keyframes fadeInThought {{
            0% {{ opacity: 0; transform: translateY(-5px); }}
            100% {{ opacity: 1; transform: translateY(0); }}
        }}
        .output-line.tool {{
            color: #20c997;
            font-weight: bold;
            background-color: rgba(32, 201, 151, 0.1);
            border-left: 3px solid #20c997;
            padding: 4px 8px;
            margin: 2px 0;
        }}
        .output-line.tool.retrieve {{
            color: #fd7e14;
            background-color: rgba(253, 126, 20, 0.15);
            border-left: 4px solid #fd7e14;
            padding: 6px 10px;
            margin: 4px 0;
            box-shadow: 0 1px 3px rgba(253, 126, 20, 0.2);
            border-radius: 4px;
            animation: fadeInRetrieve 0.5s ease;
        }}
        .output-line.tool.retrieve::before {{
            content: "📚 ";
            font-size: 1.1em;
        }}
        @keyframes fadeInRetrieve {{
            0% {{ opacity: 0; transform: scale(0.95); }}
            100% {{ opacity: 1; transform: scale(1); }}
        }}
        .output-line.tool_result {{
            color: #17a2b8;
            background-color: rgba(23, 162, 184, 0.1);
            border-left: 3px solid #17a2b8;
            padding: 4px 8px;
            margin: 2px 0;
        }}
        .output-line.agent_output {{
            color: #495057;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.5;
            animation: fadeIn 0.3s ease-in;
        }}
        .output-line.status {{
            color: #6c757d;
            font-style: italic;
            background-color: rgba(108, 117, 125, 0.1);
            padding: 4px 8px;
            margin: 2px 0;
            animation: slideIn 0.3s ease-out;
        }}
        .output-line.completion {{
            color: #28a745;
            font-weight: bold;
            background-color: rgba(40, 167, 69, 0.1);
            border-left: 3px solid #28a745;
            padding: 4px 8px;
            margin: 4px 0;
            animation: bounceIn 0.5s ease-out;
        }}
        .output-line.final {{
            color: #007bff;
            font-weight: bold;
            background-color: rgba(0, 123, 255, 0.1);
            border-left: 3px solid #007bff;
            padding: 8px;
            margin: 4px 0;
            border-radius: 4px;
            animation: bounceIn 0.5s ease-out;
        }}
        .output-line.error {{
            color: #dc3545;
            background-color: rgba(248, 113, 113, 0.1);
            border-left: 3px solid #f87171;
            padding: 8px;
            margin: 4px 0;
            border-radius: 4px;
            animation: shakeIn 0.5s ease-out;
        }}
        .status {{
            text-align: center;
            margin: 10px 0;
            font-style: italic;
            transition: color 0.3s ease;
        }}

        /* Animations */
        @keyframes fadeIn {{
            from {{ opacity: 0; }}
            to {{ opacity: 1; }}
        }}

        @keyframes slideIn {{
            from {{
                opacity: 0;
                transform: translateX(-20px);
            }}
            to {{
                opacity: 1;
                transform: translateX(0);
            }}
        }}

        @keyframes bounceIn {{
            0% {{
                opacity: 0;
                transform: scale(0.8);
            }}
            50% {{
                opacity: 1;
                transform: scale(1.05);
            }}
            100% {{
                opacity: 1;
                transform: scale(1);
            }}
        }}

        @keyframes shakeIn {{
            0% {{ transform: translateX(0); }}
            25% {{ transform: translateX(-5px); }}
            50% {{ transform: translateX(5px); }}
            75% {{ transform: translateX(-3px); }}
            100% {{ transform: translateX(0); }}
        }}

        /* Real-time indicator */
        .streaming-indicator {{
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #28a745;
            border-radius: 50%;
            margin-left: 5px;
            animation: pulse 1.5s infinite;
        }}

        @keyframes pulse {{
            0% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.3; transform: scale(1.2); }}
            100% {{ opacity: 1; transform: scale(1); }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 AWS Bedrock Browser Agent</h1>

        <div class="config-info">
            <strong>Configuration:</strong> Mode: {mode} | Model: {global_args.model}
        </div>

        <div class="input-section">
            <input type="text" id="userInput" placeholder="Enter what you'd like the agent to do..."
                   value="Make your assessment of the website http://testphp.vulnweb.com"
                   onkeypress="if(event.key==='Enter') startAgent()">
            <div style="margin: 10px 0;">
                <label for="maxLines" style="margin-right: 10px;">Max lines per tool output:</label>
                <input type="number" id="maxLines" value="5" min="1" max="50"
                       style="width: 80px; padding: 5px;">
                <span style="margin-left: 10px; font-size: 12px; color: #6c757d;">
                    Controls how many lines of tool output are shown per message
                </span>
            </div>
            <button onclick="startAgent()" id="startBtn">🚀 Start Agent</button>
            <button onclick="clearOutput()" id="clearBtn"
                    style="margin-left: 10px; background: #6c757d;">🗑️ Clear Output</button>
        </div>

        <div class="status" id="status">Ready to start...</div>

        <div class="output-section" id="output">
            <div class="output-line">Agent output will appear here...</div>
        </div>
    </div>

    <script>
        let ws = null;
        let isRunning = false;
        let streamingIndicator = null;

        function createStreamingIndicator() {{
            const indicator = document.createElement('span');
            indicator.className = 'streaming-indicator';
            indicator.title = 'Streaming in real-time';
            return indicator;
        }}

        function addStreamingIndicator() {{
            const status = document.getElementById('status');
            if (!streamingIndicator) {{
                streamingIndicator = createStreamingIndicator();
                status.appendChild(streamingIndicator);
            }}
        }}

        function removeStreamingIndicator() {{
            if (streamingIndicator && streamingIndicator.parentNode) {{
                streamingIndicator.parentNode.removeChild(streamingIndicator);
                streamingIndicator = null;
            }}
        }}

        function connectWebSocket() {{
            ws = new WebSocket(`ws://${{window.location.host}}/ws`);

            ws.onopen = function() {{
                console.log('WebSocket connected');
                const status = document.getElementById('status');
                status.textContent = 'Connected - Ready to start...';
                status.style.color = '#28a745';
            }};

            ws.onmessage = function(event) {{
                const output = document.getElementById('output');
                const line = document.createElement('div');
                line.className = 'output-line';

                try {{
                    // Try to parse as JSON (structured message)
                    const messageData = JSON.parse(event.data);

                    // Add streaming indicator for certain message types
                    if (['status', 'tool', 'agent_output'].includes(messageData.type)) {{
                        addStreamingIndicator();
                    }}

                    // Handle different message types
                    if (messageData.type === 'agent_output') {{
                        // Stream agent text output inline (no newlines)
                        line.textContent = messageData.text;
                        line.classList.add('agent_output');
                    }} else if (messageData.type === 'tool') {{
                        line.textContent = messageData.text;
                        line.classList.add('tool');
                        // Add special class for retrieve tool
                        if (messageData.text.toLowerCase().includes('retrieve')) {{
                            line.classList.add('retrieve');
                        }}
                    }} else if (messageData.type === 'tool_result') {{
                        line.textContent = messageData.text;
                        line.classList.add('tool_result');
                    }} else if (messageData.type === 'status') {{
                        line.textContent = messageData.text;
                        line.classList.add('status');
                    }} else if (messageData.type === 'completion') {{
                        line.textContent = messageData.text;
                        line.classList.add('completion');
                        removeStreamingIndicator(); // Remove indicator on completion
                    }} else if (messageData.type === 'final') {{
                        line.textContent = messageData.text;
                        line.classList.add('final');
                        removeStreamingIndicator(); // Remove indicator on final message
                    }} else if (messageData.type === 'error') {{
                        line.textContent = messageData.text;
                        line.classList.add('error');
                        removeStreamingIndicator(); // Remove indicator on error
                    }} else if (messageData.type === 'thought') {{
                        line.textContent = messageData.text;
                        line.classList.add('thought');
                    }} else {{
                        // Default handling
                        line.textContent = messageData.text;
                    }}
                }} catch (e) {{
                    // Fallback for plain text messages
                    line.textContent = event.data;
                }}

                output.appendChild(line);
                output.scrollTop = output.scrollHeight;
            }};

            ws.onclose = function() {{
                console.log('WebSocket disconnected, attempting to reconnect...');
                const status = document.getElementById('status');
                status.textContent = 'Disconnected - Reconnecting...';
                status.style.color = '#dc3545';
                setTimeout(connectWebSocket, 1000);
            }};

            ws.onerror = function(error) {{
                console.error('WebSocket error:', error);
                const status = document.getElementById('status');
                status.textContent = 'Connection error';
                status.style.color = '#dc3545';
            }};
        }}

        function clearOutput() {{
            const output = document.getElementById('output');
            output.innerHTML = '<div class="output-line">Output cleared - ' +
                               'Ready for new agent run...</div>';
        }}

        async function startAgent() {{
            if (isRunning) return;

            const userInput = document.getElementById('userInput').value;
            const maxLines = parseInt(document.getElementById('maxLines').value) || 5;
            const startBtn = document.getElementById('startBtn');
            const status = document.getElementById('status');
            const output = document.getElementById('output');

            if (!userInput.trim()) {{
                alert('Please enter some input for the agent');
                return;
            }}

            isRunning = true;
            startBtn.disabled = true;
            startBtn.textContent = '⏳ Running...';
            status.textContent = 'Agent is running...';
            status.style.color = '#007bff';
            output.innerHTML = '<div class="output-line status">🚀 Initializing agent...</div>';

            try {{
                const response = await fetch('/run-agent', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                    }},
                    body: JSON.stringify({{
                        input: userInput,
                        max_lines: maxLines
                    }})
                }});

                const result = await response.json();
                status.textContent = result.status === 'completed' ?
                    '✅ Agent execution completed' :
                    `❌ Error: ${{result.message}}`;
                status.style.color = result.status === 'completed' ? '#28a745' : '#dc3545';

            }} catch (error) {{
                status.textContent = `❌ Network Error: ${{error.message}}`;
                status.style.color = '#dc3545';
            }} finally {{
                isRunning = false;
                startBtn.disabled = false;
                startBtn.textContent = '🚀 Start Agent';
            }}
        }}

        // Connect WebSocket on page load
        connectWebSocket();
    </script>
</body>
</html>
    """
    )


@app.post("/run-agent")
async def run_agent(request_data: dict):
    logger = get_logger(__name__)
    user_input = request_data.get("input", "")
    max_lines = request_data.get("max_lines", 5)  # Default to 5 lines

    if not user_input.strip():
        logger.warning("Agent run attempted with no input provided")
        return {"status": "error", "message": "No input provided"}

    logger.info("Starting agent run with input: %s...", user_input[:100])
    logger.info("Max lines configured: %s", max_lines)

    try:
        # Create MCP clients using Strands framework
        def create_playwright_transport():
            return stdio_client(playwright_server_params)

        def create_filesystem_transport():
            return stdio_client(filesystem_server_params)

        playwright_mcp_client = MCPClient(transport_callable=create_playwright_transport)
        filesystem_mcp_client = MCPClient(transport_callable=create_filesystem_transport)

        try:
            # Setup Bedrock model with streaming enabled
            bedrock_model = BedrockModel(model_id=global_args.model, streaming=False)

            # Start with built-in tools including knowledge base retrieval
            all_tools = [retrieve]

            # Use MCP clients in context managers to get tools
            with playwright_mcp_client, filesystem_mcp_client:
                # Get tools from both MCP servers
                playwright_tools = playwright_mcp_client.list_tools_sync()
                filesystem_tools = filesystem_mcp_client.list_tools_sync()

                # Combine all tools including retrieve
                all_tools.extend(playwright_tools + filesystem_tools)

                # Create the main agent with all tools but WITHOUT callback handler
                # We'll use stream_async instead for better real-time streaming
                agent = Agent(
                    model=bedrock_model,
                    system_prompt=system_prompt,
                    tools=all_tools,
                    callback_handler=None,  # Disable default callback handler
                )

                # Send initial message to frontend
                await manager.send_message("🚀 Starting agent execution...", "status")

                # Send progress update
                await manager.send_message("🔧 Initializing tools and model...", "status")

                # Use async streaming for real-time updates
                try:
                    await manager.send_message("🤖 Agent started thinking...", "status")

                    # Get async stream from agent
                    agent_stream = agent.stream_async(user_input)

                    # Process events as they arrive in real-time
                    async for event in agent_stream:
                        if "data" in event:
                            # Stream agent text output
                            output = event["data"]
                            await manager.send_message(output, "agent_output")

                        elif "thinking" in event or "thought" in event:
                            # Agent is thinking/reasoning - display thought bubble
                            thought_content = event.get("thinking") or event.get("thought")
                            if thought_content:
                                await manager.send_message(thought_content, "thought")

                        elif "current_tool_use" in event and event["current_tool_use"].get("name"):
                            # Tool usage information
                            tool_info = event["current_tool_use"]
                            tool_name = tool_info.get("name", "Unknown")
                            tool_args = tool_info.get("input", {})

                            # Send detailed tool usage message
                            tool_message = f"🔧 Using tool: {tool_name}"
                            if tool_args:
                                args_preview = str(tool_args)[:100]
                                if len(str(tool_args)) > 100:
                                    args_preview += "..."
                                tool_message += f" with args: {args_preview}"

                            # Use special type for retrieval tools
                            message_type = "tool"
                            # Frontend will detect "retrieve" in the message and apply
                            # special styling
                            await manager.send_message(tool_message, message_type)

                        elif "current_tool_result" in event:
                            # Tool result information with truncation
                            tool_result = event["current_tool_result"]
                            if tool_result:
                                truncated_result = truncate_long_output(str(tool_result), max_lines)
                                result_message = f"✅ Tool result: {truncated_result}"
                            else:
                                result_message = "✅ Tool result: No result"

                            await manager.send_message(result_message, "tool_result")

                    await manager.send_message("🎯 Agent finished processing", "status")

                except Exception as agent_error:
                    await manager.send_message(
                        f"❌ Agent execution error: {agent_error!s}", "error"
                    )
                    raise

                await manager.send_message("\n✅ Assessment completed!", "completion")
                logger.info("Agent execution completed successfully")

        except Exception as e:
            logger.error("Error during agent execution: %s", e, exc_info=True)
            raise

        return {
            "status": "completed",
            "message": "Agent execution completed successfully",
        }

    except Exception as e:
        logger.error("Agent execution failed: %s", e, exc_info=True)
        await manager.send_message(f"Error: {e!s}\n", "error")
        print(f"Error during agent execution: {e!s}", file=sys.__stderr__)
        traceback.print_exc(file=sys.__stderr__)
        return {"status": "error", "message": str(e)}


# Set knowledge base ID from args when available
def set_knowledge_base_env(knowledge_base_id: str) -> None:
    """Set the KNOWLEDGE_BASE_ID environment variable for the retrieve tool."""
    os.environ["KNOWLEDGE_BASE_ID"] = knowledge_base_id


def truncate_long_output(text, max_lines=5):
    """Truncate text to max_lines if it's too long."""
    if not text or not text.strip():
        return text

    lines = text.split("\n")
    if len(lines) > max_lines:
        truncated_lines = lines[:max_lines]
        truncated_lines.append(f"... [truncated {len(lines) - max_lines} more lines]")
        return "\n".join(truncated_lines)
    return text


if __name__ == "__main__":
    # Parse command line arguments
    global_args = parse_web_args()

    # Setup logging configuration
    log_config = setup_logging(logs_dir="./logs")
    logger = get_logger(__name__)

    # Get knowledge base ID from environment variable
    knowledge_base_id = os.getenv("KNOWLEDGE_BASE_ID")
    if knowledge_base_id:
        # Set knowledge base ID for retrieve tool
        set_knowledge_base_env(knowledge_base_id)

    # Print configuration info
    if global_args.use_docker_mcps:
        mode = "Local (Docker - Headless)"
    elif global_args.headless:
        mode = "Local (Headless)"
    else:
        mode = "Local (Headed)"

    print("=== AWS Bedrock Browser Agent Web Interface ===")
    print(f"Mode: {mode}")
    print(f"Model: {global_args.model}")
    print(f"Knowledge Base: {knowledge_base_id or 'Not configured'}")
    print(f"Server: {global_args.host}:{global_args.port}")

    logger.info("AWS Bedrock Browser Agent Web Interface starting")
    logger.info("Mode: %s", mode)
    logger.info("Model: %s", global_args.model)
    logger.info("Knowledge Base: %s", knowledge_base_id or 'Not configured')
    logger.info("Server: %s:%s", global_args.host, global_args.port)
    logger.info("Logs: %s", log_config["log_file"])

    uvicorn.run(app, host=global_args.host, port=global_args.port)
