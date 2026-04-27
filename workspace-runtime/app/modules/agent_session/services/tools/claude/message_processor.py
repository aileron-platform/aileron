"""
SDK Message Processor.

References agor-main's message-processor.ts
Processes Claude Agent SDK messages and converts them to structured events.

Responsibilities:
- Handles all SDK message types
- Tracks conversation state(session ID, message count, activity time)
- Sends streaming events(real-time UI updates)
- Generates structured events(database persistence)
"""

import logging
import time

logger = logging.getLogger(__name__)
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)
from claude_agent_sdk.types import StreamEvent

from app.modules.agent_session.domain.enums import MessageRole
from app.modules.agent_session.services.tools.base.types import (
    CompleteEvent,
    EndEvent,
    PartialEvent,
    ProcessedEvent,
    ResultEvent,
    ThinkingCompleteEvent,
    ThinkingPartialEvent,
    TokenUsage,
    ToolCompleteEvent,
    ToolStartEvent,
)


@dataclass
class ProcessorOptions:
    """Processor options."""
    
    session_id: str
    existing_sdk_session_id: Optional[str] = None
    enable_token_streaming: bool = True
    idle_timeout_ms: int = 300000  # 5 minutes


@dataclass
class ContentBlockInfo:
    """Content block info(for tracking tool_complete)."""
    
    index: int
    type: str  # 'text', 'tool_use', 'thinking'
    tool_use_id: Optional[str] = None
    tool_name: Optional[str] = None


@dataclass
class ProcessorState:
    """Processor state."""

    session_id: str
    existing_sdk_session_id: Optional[str]
    captured_agent_session_id: Optional[str] = None
    message_count: int = 0
    last_activity_time: float = field(default_factory=time.time)
    last_assistant_message_time: float = field(default_factory=time.time)
    resolved_model: Optional[str] = None
    enable_token_streaming: bool = True
    idle_timeout_ms: int = 300000
    content_block_stack: List[ContentBlockInfo] = field(default_factory=list)
    tool_input_chunk_count: int = 0
    # Track tool_use_id -> tool_name mapping, for handling tool_result
    tool_use_registry: Dict[str, str] = field(default_factory=dict)


class SDKMessageProcessor:
    """
    SDK Message Processor.
    
    Stateful processor that handles SDK messages and sends structured events.
    One instance per query/conversation.
    """
    
    def __init__(self, options: ProcessorOptions):
        """Initialize Processor."""
        self.state = ProcessorState(
            session_id=options.session_id,
            existing_sdk_session_id=options.existing_sdk_session_id,
            enable_token_streaming=options.enable_token_streaming,
            idle_timeout_ms=options.idle_timeout_ms,
        )
    
    async def process(self, msg: Any) -> List[ProcessedEvent]:
        """
        Process SDK message and return 0 or more events.

        Args:
            msg: SDK message

        Returns:
            Event list
        """
        self.state.message_count += 1
        self.state.last_activity_time = time.time()

        events: List[ProcessedEvent] = []

        # Handle different message types
        if isinstance(msg, AssistantMessage):
            events.extend(await self._handle_assistant_message(msg))
        elif isinstance(msg, ResultMessage):
            events.extend(await self._handle_result_message(msg))
        elif isinstance(msg, UserMessage):
            events.extend(await self._handle_user_message(msg))
        elif isinstance(msg, SystemMessage):
            events.extend(await self._handle_system_message(msg))
        elif isinstance(msg, StreamEvent):
            events.extend(await self._handle_stream_event(msg))

        return events
    
    def has_timed_out(self) -> bool:
        """Check if timeout has occurred."""
        idle_time_ms = (time.time() - self.state.last_activity_time) * 1000
        return idle_time_ms > self.state.idle_timeout_ms
    
    def get_state(self) -> ProcessorState:
        """Get current state."""
        return self.state

    async def _handle_assistant_message(
        self, msg: AssistantMessage
    ) -> List[ProcessedEvent]:
        """Handle complete assistant message."""
        events: List[ProcessedEvent] = []

        # Process content blocks
        content_blocks = []
        tool_uses = []

        for block in msg.content:
            if isinstance(block, TextBlock):
                content_blocks.append({"type": "text", "text": block.text})
            elif isinstance(block, ThinkingBlock):
                content_blocks.append({"type": "thinking", "thinking": block.thinking})
                # Send thinking complete event
                events.append(ThinkingCompleteEvent())
            elif isinstance(block, ToolUseBlock):
                content_blocks.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
                tool_uses.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
                # Register tool_use_id -> tool_name mapping
                self.state.tool_use_registry[block.id] = block.name
                # Send tool start event
                events.append(ToolStartEvent(
                    tool_use_id=block.id,
                    tool_name=block.name,
                ))
            elif isinstance(block, ToolResultBlock):
                # Check corresponding tool_name, special handling for AskUserQuestion
                tool_name = self.state.tool_use_registry.get(block.tool_use_id)
                # AskUserQuestion uses PermissionResultAllow + updated_input to return user answer
                # Ensure user answer is not marked as error
                is_error = block.is_error
                if tool_name == "AskUserQuestion":
                    is_error = False
                content_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": block.tool_use_id,
                    "content": block.content,
                    "is_error": is_error,
                })
                # Send tool complete event
                events.append(ToolCompleteEvent(tool_use_id=block.tool_use_id))

        # Send complete event (with full content blocks)
        events.append(CompleteEvent(
            role=MessageRole.ASSISTANT,
            content=content_blocks,
            tool_uses=tool_uses if tool_uses else None,
            resolved_model=self.state.resolved_model,
        ))

        return events

    async def _handle_result_message(
        self, msg: ResultMessage
    ) -> List[ProcessedEvent]:
        """Handle result message."""
        events: List[ProcessedEvent] = []

        # Capture agent session ID
        if msg.session_id and not self.state.captured_agent_session_id:
            self.state.captured_agent_session_id = msg.session_id

        # Extract token usage
        token_usage = None
        if msg.usage:
            token_usage = TokenUsage(
                input=msg.usage.get("input_tokens", 0),
                output=msg.usage.get("output_tokens", 0),
                cache_read=msg.usage.get("cache_read_input_tokens"),
                cache_creation=msg.usage.get("cache_creation_input_tokens"),
            )

        # Extract structured_output (SDK docs: JSON results only appear in ResultMessage)
        structured_output = getattr(msg, "structured_output", None)
        if structured_output is not None:
            logger.info(
                "ResultMessage contains structured_output for session %s",
                self.state.session_id[:8],
            )

        # Build raw SDK message
        raw_sdk_message = {
            "type": "claude",
            "session_id": msg.session_id,
            "usage": msg.usage or {},
            "total_cost_usd": msg.total_cost_usd,
            "duration_ms": msg.duration_ms,
            "duration_api_ms": msg.duration_api_ms,
            "num_turns": msg.num_turns,
        }
        if structured_output is not None:
            raw_sdk_message["structured_output"] = structured_output

        # Send result event
        events.append(ResultEvent(
            raw_sdk_message=raw_sdk_message,
            token_usage=token_usage,
            structured_output=structured_output,
        ))

        # Send end event
        events.append(EndEvent(reason="result"))

        return events

    async def _handle_user_message(
        self, msg: UserMessage
    ) -> List[ProcessedEvent]:
        """Handle user message."""
        events: List[ProcessedEvent] = []

        # Process content blocks
        content_blocks = []
        for block in msg.content:
            if isinstance(block, TextBlock):
                content_blocks.append({"type": "text", "text": block.text})
            elif isinstance(block, ToolResultBlock):
                # Check corresponding tool_name, special handling for AskUserQuestion
                tool_name = self.state.tool_use_registry.get(block.tool_use_id)
                # AskUserQuestion uses PermissionResultAllow + updated_input to return user answer
                # Ensure user answer is not marked as error
                is_error = block.is_error
                if tool_name == "AskUserQuestion":
                    is_error = False
                # Handle tool result
                content_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": block.tool_use_id,
                    "content": block.content,
                    "is_error": is_error,
                })
                # Send tool complete event
                events.append(ToolCompleteEvent(tool_use_id=block.tool_use_id))

        # Send complete event (only if has content)
        if content_blocks:
            events.append(CompleteEvent(
                role=MessageRole.USER,
                content=content_blocks,
            ))

        return events

    async def _handle_stream_event(
        self, msg: StreamEvent
    ) -> List[ProcessedEvent]:
        """Handle stream event.

        StreamEvent format:
        - uuid: str (event UUID)
        - session_id: str (session ID)
        - event: dict (raw Anthropic API stream event)
        - parent_tool_use_id: Optional[str]
        """
        if not self.state.enable_token_streaming:
            return []  # Streaming disabled

        events: List[ProcessedEvent] = []
        event = msg.event

        event_type = event.get("type")

        # Message start event - capture model
        if event_type == "message_start":
            message = event.get("message", {})
            if message.get("model"):
                self.state.resolved_model = message["model"]

        # Content block start (text, tool_use, or thinking)
        elif event_type == "content_block_start":
            block = event.get("content_block", {})
            block_index = event.get("index", 0)
            block_type = block.get("type")

            if block_type == "tool_use":
                tool_name = block.get("name", "")
                tool_id = block.get("id", "")

                # Track this tool_use block
                self.state.content_block_stack.append(ContentBlockInfo(
                    index=block_index,
                    type="tool_use",
                    tool_use_id=tool_id,
                    tool_name=tool_name,
                ))

                # Register tool_use_id -> tool_name mapping (for tool_result handling)
                self.state.tool_use_registry[tool_id] = tool_name

                events.append(ToolStartEvent(
                    tool_use_id=tool_id,
                    tool_name=tool_name,
                ))

            elif block_type == "thinking":
                self.state.content_block_stack.append(ContentBlockInfo(
                    index=block_index,
                    type="thinking",
                ))

            elif block_type == "text":
                self.state.content_block_stack.append(ContentBlockInfo(
                    index=block_index,
                    type="text",
                ))

        # Content block delta (streaming text, tool input, or thinking)
        elif event_type == "content_block_delta":
            delta = event.get("delta", {})
            delta_type = delta.get("type")

            if delta_type == "text_delta":
                text_chunk = delta.get("text", "")
                events.append(PartialEvent(
                    text=text_chunk,
                    resolved_model=self.state.resolved_model,
                ))

            elif delta_type == "thinking_delta":
                thinking_chunk = delta.get("thinking", "")
                events.append(ThinkingPartialEvent(
                    thinking_chunk=thinking_chunk,
                ))

            elif delta_type == "input_json_delta":
                # Tool input is being streamed - log occasionally
                self.state.tool_input_chunk_count += 1

        # Content block stop
        elif event_type == "content_block_stop":
            block_index = event.get("index")

            # Find the just-completed block
            completed_block = None
            for b in self.state.content_block_stack:
                if b.index == block_index:
                    completed_block = b
                    break

            if completed_block:
                if completed_block.type == "tool_use":
                    events.append(ToolCompleteEvent(tool_use_id=completed_block.tool_use_id))

                elif completed_block.type == "thinking":
                    events.append(ThinkingCompleteEvent())

        return events

    async def _handle_system_message(
        self, msg: SystemMessage
    ) -> List[ProcessedEvent]:
        """Handle system message.

        SystemMessage format:
        - subtype: str (message subtype)
        - data: dict (message data)
        """
        events: List[ProcessedEvent] = []

        # Extract model info from SystemMessage
        if msg.data:
            if "model" in msg.data:
                self.state.resolved_model = msg.data["model"]

        # SystemMessage only contains metadata, no need to create message record
        # Only send event to notify frontend
        events.append(CompleteEvent(
            role=MessageRole.SYSTEM,
            content=[{
                "type": "system",
                "subtype": msg.subtype,
                "data": msg.data,
            }],
        ))

        return events

