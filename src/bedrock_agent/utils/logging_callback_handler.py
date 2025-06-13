"""Logging-based Callback Handler for AWS Bedrock Browser Agent.

This module provides a CallbackHandler that integrates with the application's
logging system instead of printing directly to stdout.
"""

import logging
import time
from typing import Any


class LoggingCallbackHandler:
    """Comprehensive handler for streaming agent output and tool invocations to logger.
    
    Captures all event types from the Strands Agent lifecycle including:
    - Text generation events
    - Tool selection and execution  
    - Reasoning process
    - Event loop lifecycle
    - Errors and completions
    """

    def __init__(self, logger_name: str = "bedrock_agent.callback") -> None:
        """Initialize handler with a logger.

        Args:
            logger_name: Name of the logger to use (default: "bedrock_agent.callback")
        """
        self.logger = logging.getLogger(logger_name)
        self.tool_count = 0
        self.cycle_count = 0
        self.previous_tool_use: dict | None = None
        self.current_tool_name: str | None = None
        self.current_tool_id: str | None = None
        self.start_time: float | None = None
        self.cycle_start_time: float | None = None
        self.tool_start_time: float | None = None
        self.total_text_chunks = 0

    def __call__(self, **kwargs: Any) -> None:
        """Stream text output and tool invocations to logger.

        Args:
            **kwargs: Callback event data including all Strands Agent event types:
                Text Generation Events:
                - data (str): Text chunk from model output
                - complete (bool): Whether this is the final chunk
                - delta: Raw delta content from the model
                
                Tool Events:
                - current_tool_use (dict): Current tool information (toolUseId, name, input)
                - current_tool_result (Any): Result returned by the current tool
                
                Reasoning Events:
                - reasoning (bool): True for reasoning events
                - reasoningText (str): Text from reasoning process
                - reasoning_signature: Signature from reasoning process
                
                Lifecycle Events:
                - init_event_loop (bool): Event loop initializing
                - start_event_loop (bool): Event loop cycle starting
                - start (bool): New cycle starts
                - message (dict): New message created
                - event: Raw event from model stream
                - force_stop (bool): Event loop forced to stop
                - force_stop_reason (str): Reason for forced stop
        """
        try:
            # Event Loop Lifecycle Events
            self._handle_lifecycle_events(kwargs)
            
            # Reasoning Events  
            self._handle_reasoning_events(kwargs)
            
            # Text Generation Events
            self._handle_text_events(kwargs)
            
            # Tool Events
            self._handle_tool_events(kwargs)
            
            # Message Events
            self._handle_message_events(kwargs)
            
            # Error and Force Stop Events
            self._handle_error_events(kwargs)
            
        except Exception as e:
            # Log callback handler errors to prevent breaking agent execution
            self.logger.error(f"Error in callback handler: {e}", exc_info=True)
    
    def _handle_lifecycle_events(self, kwargs: dict) -> None:
        """Handle event loop lifecycle events."""
        if kwargs.get("init_event_loop", False):
            self.start_time = time.time()
            self.logger.info("🔄 Event loop initialized")
        
        if kwargs.get("start_event_loop", False):
            self.cycle_start_time = time.time()
            self.logger.info("▶️ Event loop cycle starting")
        
        if kwargs.get("start", False):
            self.cycle_count += 1
            if self.cycle_start_time:
                cycle_duration = time.time() - self.cycle_start_time
                self.logger.info(f"📝 New cycle started (#{self.cycle_count}) - Previous cycle: {cycle_duration:.2f}s")
            else:
                self.logger.info(f"📝 New cycle started (#{self.cycle_count})")
            self.cycle_start_time = time.time()
    
    def _handle_reasoning_events(self, kwargs: dict) -> None:
        """Handle reasoning and thinking events."""
        if kwargs.get("reasoning", False):
            self.logger.info("🧠 Agent reasoning phase")
        
        reasoning_text = kwargs.get("reasoningText")
        if reasoning_text:
            self.logger.info("💭 Agent Reasoning: %s", reasoning_text)
        
        reasoning_signature = kwargs.get("reasoning_signature")
        if reasoning_signature:
            self.logger.debug(f"🔍 Reasoning Signature: {reasoning_signature}")
    
    def _handle_text_events(self, kwargs: dict) -> None:
        """Handle text generation events."""
        data = kwargs.get("data", "")
        complete = kwargs.get("complete", False)
        delta = kwargs.get("delta")
        
        if data:
            self.total_text_chunks += 1
            # For incomplete responses, log as debug to avoid spam
            # For complete responses, log as info for better visibility
            if complete:
                self.logger.info(f"📝 Agent Response (complete): {data}")
                self.logger.debug(f"📊 Total text chunks received: {self.total_text_chunks}")
            else:
                # Log streaming text with chunk count for monitoring
                chunk_info = f"chunk #{self.total_text_chunks}"
                self.logger.debug(f"📟 Agent Response (streaming {chunk_info}): {data}")
        
        if delta:
            self.logger.debug(f"🔄 Raw Delta: {delta}")
    
    def _handle_tool_events(self, kwargs: dict) -> None:
        """Handle tool selection and execution events."""
        current_tool_use = kwargs.get("current_tool_use", {})
        current_tool_result = kwargs.get("current_tool_result")
        
        # Handle tool usage information
        if current_tool_use and current_tool_use.get("name"):
            tool_name = current_tool_use.get("name", "Unknown tool")
            tool_use_id = current_tool_use.get("toolUseId", current_tool_use.get("id", ""))
            
            # Only log if it's a new tool usage (avoid duplicates)
            if self.previous_tool_use != current_tool_use:
                self.previous_tool_use = current_tool_use
                self.current_tool_name = tool_name
                self.current_tool_id = tool_use_id
                self.tool_start_time = time.time()
                self.tool_count += 1
                
                # Extract tool input information
                tool_input = current_tool_use.get("input", {})
                
                # Log tool usage with structured information
                tool_info = f"🔧 Tool #{self.tool_count}: {tool_name}"
                if tool_use_id:
                    tool_info += f" (ID: {tool_use_id})"
                
                self.logger.info(tool_info)
                
                # Log tool input parameters at debug level for troubleshooting
                if tool_input:
                    self.logger.debug(f"📋 Tool Input for {tool_name}: {tool_input}")
        
        # Handle tool result information
        if current_tool_result is not None:
            self._handle_tool_result(current_tool_result, current_tool_use)
    
    def _handle_tool_result(self, tool_result: Any, current_tool_use: dict) -> None:
        """Handle tool result logging with proper formatting."""
        # Convert tool result to string for logging
        result_str = str(tool_result)
        
        # Use the stored tool name for better context, fall back to current tool use
        tool_name_for_result = self.current_tool_name or "Unknown tool"
        if current_tool_use and current_tool_use.get("name"):
            tool_name_for_result = current_tool_use.get("name")
        
        tool_id_info = ""
        if self.current_tool_id:
            tool_id_info = f" (ID: {self.current_tool_id})"
        
        # Calculate tool execution time if available
        timing_info = ""
        if self.tool_start_time:
            execution_time = time.time() - self.tool_start_time
            timing_info = f" - Execution time: {execution_time:.2f}s"
        
        # Truncate very long results for readability in info logs, but keep full result in debug
        max_result_length = 500
        if len(result_str) > max_result_length:
            truncated_result = result_str[:max_result_length] + "... (truncated)"
            self.logger.info(f"✅ Tool Result from {tool_name_for_result}{tool_id_info}: {truncated_result}{timing_info}")
            self.logger.debug(f"📄 Tool Result from {tool_name_for_result}{tool_id_info} (full): {result_str}")
        else:
            self.logger.info(f"✅ Tool Result from {tool_name_for_result}{tool_id_info}: {result_str}{timing_info}")
    
    def _handle_message_events(self, kwargs: dict) -> None:
        """Handle message creation events."""
        message = kwargs.get("message")
        if message:
            role = message.get("role", "unknown")
            content_preview = str(message.get("content", ""))[:100]
            if len(content_preview) > 100:
                content_preview += "..."
            
            self.logger.info(f"📬 New message created - Role: {role}, Content: {content_preview}")
            self.logger.debug(f"📋 Full message: {message}")
    
    def _handle_error_events(self, kwargs: dict) -> None:
        """Handle error and force stop events."""
        if kwargs.get("force_stop", False):
            reason = kwargs.get("force_stop_reason", "unknown reason")
            self.logger.warning(f"🛑 Event loop force-stopped: {reason}")
        
        if kwargs.get("complete", False):
            # Calculate total execution time if available
            timing_info = ""
            if self.start_time:
                total_time = time.time() - self.start_time
                timing_info = f" - Total execution time: {total_time:.2f}s"
            
            stats_info = f" - Cycles: {self.cycle_count}, Tools: {self.tool_count}, Text chunks: {self.total_text_chunks}"
            self.logger.info(f"✅ Agent cycle completed{timing_info}{stats_info}")
        
        # Handle raw events for debugging if needed
        event = kwargs.get("event")
        if event and self.logger.isEnabledFor(logging.DEBUG):
            # Only log raw events at debug level to avoid noise
            self.logger.debug(f"🔍 Raw Event: {event}")
    
    def get_execution_summary(self) -> str:
        """Get a summary of the agent execution for logging purposes."""
        summary_parts = []
        
        if self.start_time:
            total_time = time.time() - self.start_time
            summary_parts.append(f"Total time: {total_time:.2f}s")
        
        summary_parts.extend([
            f"Cycles: {self.cycle_count}",
            f"Tools used: {self.tool_count}",
            f"Text chunks: {self.total_text_chunks}"
        ])
        
        return " | ".join(summary_parts)


def create_logging_callback_handler(
    logger_name: str = "bedrock_agent.callback",
) -> LoggingCallbackHandler:
    """Create a logging callback handler instance.

    Args:
        logger_name: Name of the logger to use

    Returns:
        LoggingCallbackHandler instance
    """
    return LoggingCallbackHandler(logger_name)
