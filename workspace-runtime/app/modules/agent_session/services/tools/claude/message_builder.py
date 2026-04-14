"""
訊息建構函數.

比照 agor-main 的 message-builder.ts
提供純函數用於建立各種類型的訊息。
"""

from typing import Any, Dict, List, Optional

from app.modules.agent_session.domain.enums import MessageRole, MessageType
from app.modules.agent_session.schemas.message import MessageCreate
from app.modules.agent_session.services.message_service import MessageService
from app.modules.agent_session.services.tools.base.types import TokenUsage


async def create_user_message(
    session_id: str,
    prompt: str,
    task_id: Optional[str],
    index: int,
    message_service: MessageService,
) -> Dict[str, Any]:
    """
    建立使用者訊息.
    
    Args:
        session_id: 會話 ID
        prompt: 使用者 prompt
        task_id: 任務 ID
        index: 訊息索引
        message_service: 訊息服務
    
    Returns:
        建立的訊息
    """
    data = MessageCreate(
        session_id=session_id,
        task_id=task_id,
        type=MessageType.USER,
        role=MessageRole.USER,
        content=[{"type": "text", "text": prompt}],
        index=index,
        metadata={},
    )
    
    message = await message_service.create_message(data)
    
    # 將 content 轉換為 content_blocks 格式（前端期望的格式）
    content_blocks = []
    if isinstance(message.content, str):
        content_blocks = [{"type": "text", "text": message.content}]
    elif isinstance(message.content, list):
        content_blocks = message.content
    
    return {
        "message_id": message.id,
        "session_id": message.session_id,
        "task_id": message.task_id,
        "type": message.type.value if hasattr(message.type, "value") else message.type,
        "role": message.role.value if hasattr(message.role, "value") else message.role,
        "index": message.index,
        "content_blocks": content_blocks,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


async def create_assistant_message(
    session_id: str,
    message_id: str,
    content: List[Dict[str, Any]],
    tool_uses: Optional[List[Dict[str, Any]]],
    task_id: Optional[str],
    index: int,
    resolved_model: Optional[str],
    message_service: MessageService,
    parent_tool_use_id: Optional[str] = None,
    token_usage: Optional[TokenUsage] = None,
) -> str:
    """
    建立助手訊息.

    Args:
        session_id: 會話 ID
        message_id: 訊息 ID (未使用，由 MessageService 生成)
        content: 內容區塊
        tool_uses: 工具使用
        task_id: 任務 ID
        index: 訊息索引
        resolved_model: 解析的模型名稱
        message_service: 訊息服務
        parent_tool_use_id: 父工具使用 ID
        token_usage: Token 使用量

    Returns:
        實際創建的訊息 ID
    """
    # 建立 metadata
    metadata: Dict[str, Any] = {
        "source": "claude-sdk",
    }

    if resolved_model:
        metadata["model"] = resolved_model

    if token_usage:
        # 移除 None 值
        tokens = {
            "input": token_usage.input,
            "output": token_usage.output,
        }
        if token_usage.cache_read is not None:
            tokens["cache_read"] = token_usage.cache_read
        if token_usage.cache_creation is not None:
            tokens["cache_creation"] = token_usage.cache_creation

        metadata["tokens"] = tokens

    if parent_tool_use_id:
        metadata["parent_tool_use_id"] = parent_tool_use_id

    data = MessageCreate(
        session_id=session_id,
        task_id=task_id,
        type=MessageType.ASSISTANT,
        role=MessageRole.ASSISTANT,
        content=content,
        index=index,
        metadata=metadata,
    )

    message = await message_service.create_message(data)
    return message.id


async def create_tool_result_message(
    session_id: str,
    content: List[Dict[str, Any]],
    task_id: Optional[str],
    index: int,
    message_service: MessageService,
) -> str:
    """
    建立工具結果訊息.
    
    Args:
        session_id: 會話 ID
        content: 內容區塊（包含 tool_result）
        task_id: 任務 ID
        index: 訊息索引
        message_service: 訊息服務

    Returns:
        實際創建的訊息 ID
    """
    metadata: Dict[str, Any] = {
        "source": "claude-sdk",
        "is_tool_result": True,
    }
    
    data = MessageCreate(
        session_id=session_id,
        task_id=task_id,
        type=MessageType.USER,  # Claude SDK 使用 user role 傳送 tool_result
        role=MessageRole.USER,
        content=content,
        index=index,
        metadata=metadata,
    )
    
    message = await message_service.create_message(data)
    return message.id


async def create_system_message(
    session_id: str,
    content: List[Dict[str, Any]],
    task_id: Optional[str],
    index: int,
    resolved_model: Optional[str],
    message_service: MessageService,
) -> str:
    """
    建立系統訊息.

    Args:
        session_id: 會話 ID
        content: 內容區塊
        task_id: 任務 ID
        index: 訊息索引
        resolved_model: 解析的模型名稱
        message_service: 訊息服務

    Returns:
        實際創建的訊息 ID
    """
    metadata: Dict[str, Any] = {
        "source": "claude-sdk",
    }

    if resolved_model:
        metadata["model"] = resolved_model

    data = MessageCreate(
        session_id=session_id,
        task_id=task_id,
        type=MessageType.SYSTEM,
        role=MessageRole.SYSTEM,
        content=content,
        index=index,
        metadata=metadata,
    )

    message = await message_service.create_message(data)
    return message.id

