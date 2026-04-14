"""
SDK Message Processor.

比照 agor-main 的 message-processor.ts
處理 Claude Agent SDK 訊息並轉換為結構化事件。

職責：
- 處理所有 SDK 訊息類型
- 追蹤對話狀態（session ID, 訊息計數, 活動時間）
- 發送串流事件（實時 UI 更新）
- 產生結構化事件（資料庫持久化）
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
    """Processor 選項."""
    
    session_id: str
    existing_sdk_session_id: Optional[str] = None
    enable_token_streaming: bool = True
    idle_timeout_ms: int = 300000  # 5 minutes


@dataclass
class ContentBlockInfo:
    """Content block 資訊（用於追蹤 tool_complete）."""
    
    index: int
    type: str  # 'text', 'tool_use', 'thinking'
    tool_use_id: Optional[str] = None
    tool_name: Optional[str] = None


@dataclass
class ProcessorState:
    """Processor 狀態."""

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
    # 追蹤 tool_use_id -> tool_name 的映射，用於處理 tool_result
    tool_use_registry: Dict[str, str] = field(default_factory=dict)


class SDKMessageProcessor:
    """
    SDK Message Processor.
    
    狀態化處理器，處理 SDK 訊息並發送結構化事件。
    每個 query/conversation 建立一個實例。
    """
    
    def __init__(self, options: ProcessorOptions):
        """初始化 Processor."""
        self.state = ProcessorState(
            session_id=options.session_id,
            existing_sdk_session_id=options.existing_sdk_session_id,
            enable_token_streaming=options.enable_token_streaming,
            idle_timeout_ms=options.idle_timeout_ms,
        )
    
    async def process(self, msg: Any) -> List[ProcessedEvent]:
        """
        處理 SDK 訊息並返回 0 或多個事件.

        Args:
            msg: SDK 訊息

        Returns:
            事件列表
        """
        self.state.message_count += 1
        self.state.last_activity_time = time.time()

        events: List[ProcessedEvent] = []

        # 處理不同類型的訊息
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
        """檢查是否超時."""
        idle_time_ms = (time.time() - self.state.last_activity_time) * 1000
        return idle_time_ms > self.state.idle_timeout_ms
    
    def get_state(self) -> ProcessorState:
        """取得目前狀態."""
        return self.state

    async def _handle_assistant_message(
        self, msg: AssistantMessage
    ) -> List[ProcessedEvent]:
        """處理完整助手訊息."""
        events: List[ProcessedEvent] = []

        # 處理 content blocks
        content_blocks = []
        tool_uses = []

        for block in msg.content:
            if isinstance(block, TextBlock):
                content_blocks.append({"type": "text", "text": block.text})
            elif isinstance(block, ThinkingBlock):
                content_blocks.append({"type": "thinking", "thinking": block.thinking})
                # 發送思考完成事件
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
                # 註冊 tool_use_id -> tool_name 映射
                self.state.tool_use_registry[block.id] = block.name
                # 發送工具開始事件
                events.append(ToolStartEvent(
                    tool_use_id=block.id,
                    tool_name=block.name,
                ))
            elif isinstance(block, ToolResultBlock):
                # 檢查對應的 tool_name，對 AskUserQuestion 特殊處理
                tool_name = self.state.tool_use_registry.get(block.tool_use_id)
                # AskUserQuestion 使用 PermissionResultAllow + updated_input 返回用戶答案
                # 確保用戶回答不會被標記為錯誤
                is_error = block.is_error
                if tool_name == "AskUserQuestion":
                    is_error = False
                content_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": block.tool_use_id,
                    "content": block.content,
                    "is_error": is_error,
                })
                # 發送工具完成事件
                events.append(ToolCompleteEvent(tool_use_id=block.tool_use_id))

        # 發送完成事件（包含完整的 content blocks）
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
        """處理結果訊息."""
        events: List[ProcessedEvent] = []

        # 捕獲 agent session ID
        if msg.session_id and not self.state.captured_agent_session_id:
            self.state.captured_agent_session_id = msg.session_id

        # 提取 token usage
        token_usage = None
        if msg.usage:
            token_usage = TokenUsage(
                input=msg.usage.get("input_tokens", 0),
                output=msg.usage.get("output_tokens", 0),
                cache_read=msg.usage.get("cache_read_input_tokens"),
                cache_creation=msg.usage.get("cache_creation_input_tokens"),
            )

        # 提取 structured_output（SDK 文件：JSON 結果僅出現在 ResultMessage 中）
        structured_output = getattr(msg, "structured_output", None)
        if structured_output is not None:
            logger.info(
                "ResultMessage contains structured_output for session %s",
                self.state.session_id[:8],
            )

        # 建立 raw SDK message
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

        # 發送結果事件
        events.append(ResultEvent(
            raw_sdk_message=raw_sdk_message,
            token_usage=token_usage,
            structured_output=structured_output,
        ))

        # 發送結束事件
        events.append(EndEvent(reason="result"))

        return events

    async def _handle_user_message(
        self, msg: UserMessage
    ) -> List[ProcessedEvent]:
        """處理使用者訊息."""
        events: List[ProcessedEvent] = []

        # 處理 content blocks
        content_blocks = []
        for block in msg.content:
            if isinstance(block, TextBlock):
                content_blocks.append({"type": "text", "text": block.text})
            elif isinstance(block, ToolResultBlock):
                # 檢查對應的 tool_name，對 AskUserQuestion 特殊處理
                tool_name = self.state.tool_use_registry.get(block.tool_use_id)
                # AskUserQuestion 使用 PermissionResultAllow + updated_input 返回用戶答案
                # 確保用戶回答不會被標記為錯誤
                is_error = block.is_error
                if tool_name == "AskUserQuestion":
                    is_error = False
                # 處理工具結果
                content_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": block.tool_use_id,
                    "content": block.content,
                    "is_error": is_error,
                })
                # 發送工具完成事件
                events.append(ToolCompleteEvent(tool_use_id=block.tool_use_id))

        # 發送完成事件（只在有內容時）
        if content_blocks:
            events.append(CompleteEvent(
                role=MessageRole.USER,
                content=content_blocks,
            ))

        return events

    async def _handle_stream_event(
        self, msg: StreamEvent
    ) -> List[ProcessedEvent]:
        """處理串流事件.

        StreamEvent 格式：
        - uuid: str (事件 UUID)
        - session_id: str (會話 ID)
        - event: dict (原始 Anthropic API stream 事件)
        - parent_tool_use_id: Optional[str]
        """
        if not self.state.enable_token_streaming:
            return []  # Streaming disabled

        events: List[ProcessedEvent] = []
        event = msg.event

        event_type = event.get("type")

        # Message start event - 捕獲 model
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

                # 追蹤這個 tool_use block
                self.state.content_block_stack.append(ContentBlockInfo(
                    index=block_index,
                    type="tool_use",
                    tool_use_id=tool_id,
                    tool_name=tool_name,
                ))

                # 註冊 tool_use_id -> tool_name 映射（用於 tool_result 處理）
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

            # 找到剛完成的 block
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
        """處理系統訊息.

        SystemMessage 格式：
        - subtype: str (訊息子類型)
        - data: dict (訊息資料)
        """
        events: List[ProcessedEvent] = []

        # 從 SystemMessage 中提取 model 信息
        if msg.data:
            if "model" in msg.data:
                self.state.resolved_model = msg.data["model"]

        # SystemMessage 只包含 metadata，不需要建立訊息記錄
        # 只發送事件通知前端
        events.append(CompleteEvent(
            role=MessageRole.SYSTEM,
            content=[{
                "type": "system",
                "subtype": msg.subtype,
                "data": msg.data,
            }],
        ))

        return events

