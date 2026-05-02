"""Shared message builder functions for agent tools."""

from typing import Any, Dict, List, Optional

from app.modules.agent_session.domain.enums import MessageRole, MessageType
from app.modules.agent_session.schemas.message import MessageCreate
from app.modules.agent_session.services.message_service import MessageService
from app.modules.agent_session.services.tools.base.types import TokenUsage


def _build_message_dict(message) -> Dict[str, Any]:
    """Convert a message entity to the payload expected by the frontend."""
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


def _token_usage_dict(token_usage: TokenUsage) -> Dict[str, int]:
    tokens = {
        "input": token_usage.input,
        "output": token_usage.output,
    }
    if token_usage.cache_read is not None:
        tokens["cache_read"] = token_usage.cache_read
    if token_usage.cache_creation is not None:
        tokens["cache_creation"] = token_usage.cache_creation
    return tokens


async def create_user_message(
    session_id: str,
    prompt: str,
    task_id: Optional[str],
    index: int,
    message_service: MessageService,
    source: str,
) -> Dict[str, Any]:
    """Create a user message."""
    message = await message_service.create_message(
        MessageCreate(
            session_id=session_id,
            task_id=task_id,
            type=MessageType.USER,
            role=MessageRole.USER,
            content=[{"type": "text", "text": prompt}],
            index=index,
            metadata={"source": source},
        )
    )
    return _build_message_dict(message)


async def create_assistant_message(
    session_id: str,
    content: List[Dict[str, Any]],
    task_id: Optional[str],
    index: int,
    message_service: MessageService,
    source: str,
    tool_uses: Optional[List[Dict[str, Any]]] = None,
    resolved_model: Optional[str] = None,
    parent_tool_use_id: Optional[str] = None,
    token_usage: Optional[TokenUsage] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create an assistant message."""
    message_metadata: Dict[str, Any] = {"source": source, **(metadata or {})}
    if resolved_model:
        message_metadata["model"] = resolved_model
    if token_usage:
        message_metadata["tokens"] = _token_usage_dict(token_usage)
    if parent_tool_use_id:
        message_metadata["parent_tool_use_id"] = parent_tool_use_id

    message = await message_service.create_message(
        MessageCreate(
            session_id=session_id,
            task_id=task_id,
            type=MessageType.ASSISTANT,
            role=MessageRole.ASSISTANT,
            content=content,
            index=index,
            metadata=message_metadata,
            tool_uses=tool_uses or [],
        )
    )
    return _build_message_dict(message)


async def create_tool_result_message(
    session_id: str,
    content: List[Dict[str, Any]],
    task_id: Optional[str],
    index: int,
    message_service: MessageService,
    source: str,
) -> Dict[str, Any]:
    """Create a user-role tool result message."""
    message = await message_service.create_message(
        MessageCreate(
            session_id=session_id,
            task_id=task_id,
            type=MessageType.USER,
            role=MessageRole.USER,
            content=content,
            index=index,
            metadata={"source": source, "is_tool_result": True},
        )
    )
    return _build_message_dict(message)


async def create_system_message(
    session_id: str,
    content: List[Dict[str, Any]],
    task_id: Optional[str],
    index: int,
    resolved_model: Optional[str],
    message_service: MessageService,
    source: str,
) -> Dict[str, Any]:
    """Create a system message."""
    metadata: Dict[str, Any] = {"source": source}
    if resolved_model:
        metadata["model"] = resolved_model

    message = await message_service.create_message(
        MessageCreate(
            session_id=session_id,
            task_id=task_id,
            type=MessageType.SYSTEM,
            role=MessageRole.SYSTEM,
            content=content,
            index=index,
            metadata=metadata,
        )
    )
    return _build_message_dict(message)
