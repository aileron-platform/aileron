"""
ACP message builder functions.

Provides common methods for creating user/assistant messages.
"""

from typing import Any, Dict, List, Optional

from app.modules.agent_session.domain.enums import MessageRole, MessageType
from app.modules.agent_session.schemas.message import MessageCreate
from app.modules.agent_session.services.message_service import MessageService


async def create_user_message(
    session_id: str,
    prompt: str,
    task_id: Optional[str],
    index: int,
    message_service: MessageService,
) -> Dict[str, Any]:
    """Create user message."""
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
    content: List[Dict[str, Any]],
    task_id: Optional[str],
    index: int,
    message_service: MessageService,
    tool_uses: Optional[List[Dict[str, Any]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create assistant message and return WebSocket-compatible payload."""
    data = MessageCreate(
        session_id=session_id,
        task_id=task_id,
        type=MessageType.ASSISTANT,
        role=MessageRole.ASSISTANT,
        content=content,
        index=index,
        metadata={"source": "acp", **(metadata or {})},
        tool_uses=tool_uses or [],
    )

    message = await message_service.create_message(data)
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
