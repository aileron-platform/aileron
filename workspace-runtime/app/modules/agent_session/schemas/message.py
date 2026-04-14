"""Message Schema 定義.

定義訊息相關的 API 請求/回應模型。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from ..domain.enums import MessageRole, MessageStatus, MessageType
from .content_blocks import ContentBlock


# === 請求模型 ===


class ToolUseCreate(BaseModel):
    """工具使用建立請求."""

    id: str
    name: str
    input: Dict[str, Any] = Field(default_factory=dict)


class MessageCreate(BaseModel):
    """建立訊息請求."""

    session_id: str
    task_id: Optional[str] = None
    type: MessageType = MessageType.USER
    role: MessageRole = MessageRole.USER
    content: Union[str, List[Dict[str, Any]], Dict[str, Any]] = ""
    tool_uses: List[ToolUseCreate] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    parent_tool_use_id: Optional[str] = None


class MessageUpdate(BaseModel):
    """更新訊息請求."""

    content: Optional[Union[str, List[Dict[str, Any]], Dict[str, Any]]] = None
    tool_uses: Optional[List[ToolUseCreate]] = None
    metadata: Optional[Dict[str, Any]] = None


class MessageQuery(BaseModel):
    """訊息查詢參數."""

    session_id: Optional[str] = None
    task_id: Optional[str] = None
    type: Optional[MessageType] = None
    role: Optional[MessageRole] = None
    limit: int = Field(100, ge=1, le=500)
    offset: int = Field(0, ge=0)


class MessageBulkCreate(BaseModel):
    """批次建立訊息請求."""

    messages: List[MessageCreate]


class QueueMessageRequest(BaseModel):
    """佇列訊息請求."""

    prompt: str


# === 回應模型 ===


class ToolUseResponse(BaseModel):
    """工具使用回應."""

    id: str
    name: str
    input: Dict[str, Any] = Field(default_factory=dict)


class PermissionRequestContentResponse(BaseModel):
    """權限請求內容回應."""

    request_id: str
    tool_name: str
    tool_input: Dict[str, Any]
    tool_use_id: Optional[str] = None
    tool_call_id: Optional[str] = None
    decision_type: Optional[str] = None
    outcome: Optional[str] = None
    option_id: Optional[str] = None
    options: Optional[List[Dict[str, Any]]] = None
    raw_tool_call: Optional[Dict[str, Any]] = None
    status: str = "pending"
    scope: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    reason: Optional[str] = None
    content: Optional[str] = None


class TokenUsage(BaseModel):
    """Token 使用量."""

    input: int = 0
    output: int = 0
    cache_read: Optional[int] = None
    cache_creation: Optional[int] = None


class MessageMetadataResponse(BaseModel):
    """訊息元數據回應."""

    model: Optional[str] = None
    tokens: Optional[TokenUsage] = None
    original_id: Optional[str] = None
    parent_id: Optional[str] = None
    is_meta: Optional[bool] = None
    source: Optional[str] = None


class MessageResponse(BaseModel):
    """訊息回應."""

    message_id: str  # 前端期望的欄位名稱
    created_at: datetime
    session_id: str
    task_id: Optional[str] = None
    type: MessageType
    role: MessageRole
    index: int
    timestamp: Optional[datetime] = None
    content_preview: Optional[str] = None
    parent_tool_use_id: Optional[str] = None
    status: Optional[MessageStatus] = None
    queue_position: Optional[int] = None

    # Data blob 欄位
    content: Union[str, List[Dict[str, Any]], PermissionRequestContentResponse, None] = None
    content_blocks: Optional[List[Dict[str, Any]]] = None  # 前端期望的格式
    tool_uses: List[ToolUseResponse] = Field(default_factory=list)
    metadata: Optional[MessageMetadataResponse] = None

    model_config = {"from_attributes": True, "populate_by_name": True}

    @classmethod
    def from_entity(cls, entity) -> "MessageResponse":
        """從領域實體建立回應."""
        # 處理 content
        content = entity.content
        if hasattr(content, "to_dict"):
            # PermissionRequestContent (object)
            content = PermissionRequestContentResponse(
                request_id=content.request_id,
                tool_name=content.tool_name,
                tool_input=content.tool_input,
                tool_use_id=content.tool_use_id,
                tool_call_id=content.tool_call_id,
                decision_type=content.decision_type,
                outcome=content.outcome,
                option_id=content.option_id,
                options=content.options,
                raw_tool_call=content.raw_tool_call,
                status=content.status.value if hasattr(content.status, "value") else str(content.status),
                scope=content.scope.value if content.scope and hasattr(content.scope, "value") else content.scope,
                approved_by=content.approved_by,
                approved_at=content.approved_at,
                reason=content.reason,
                content=content.content,
            )
        elif isinstance(content, dict) and "tool_name" in content:
            # PermissionRequestContent (dict) - 防禦性處理
            # 驗證必要欄位
            missing_fields = []
            if not content.get("request_id"):
                missing_fields.append("request_id")
            if not content.get("tool_name"):
                missing_fields.append("tool_name")

            if missing_fields:
                logger.error(
                    f"Permission request dict missing required fields: {missing_fields}",
                    extra={
                        "entity_id": entity.id,
                        "session_id": entity.session_id,
                        "missing_fields": missing_fields,
                        "available_keys": list(content.keys()),
                    }
                )

            logger.warning(
                "Converting dict to PermissionRequestContent - this indicates a data serialization issue",
                extra={
                    "entity_id": entity.id,
                    "session_id": entity.session_id,
                    "task_id": entity.task_id,
                    "content_keys": list(content.keys()),
                    "has_required_fields": len(missing_fields) == 0,
                }
            )

            content = PermissionRequestContentResponse(
                request_id=content.get("request_id", ""),
                tool_name=content.get("tool_name", ""),
                tool_input=content.get("tool_input", {}),
                tool_use_id=content.get("tool_use_id"),
                tool_call_id=content.get("tool_call_id"),
                decision_type=content.get("decision_type"),
                outcome=content.get("outcome"),
                option_id=content.get("option_id"),
                options=content.get("options"),
                raw_tool_call=content.get("raw_tool_call"),
                status=content.get("status", "pending"),
                scope=content.get("scope"),
                approved_by=content.get("approved_by"),
                approved_at=content.get("approved_at"),
                reason=content.get("reason"),
                content=content.get("content"),
            )

        # 處理 tool_uses
        tool_uses = []
        for tu in entity.tool_uses:
            tool_uses.append(ToolUseResponse(
                id=tu.id,
                name=tu.name,
                input=tu.input,
            ))

        # 處理 metadata
        metadata = None
        if entity.metadata:
            meta = entity.metadata
            tokens = meta.get("tokens")
            metadata = MessageMetadataResponse(
                model=meta.get("model"),
                tokens=tokens,
                original_id=meta.get("original_id"),
                parent_id=meta.get("parent_id"),
                is_meta=meta.get("is_meta"),
                source=meta.get("source"),
            )

        # 生成 content_blocks
        content_blocks = None
        if isinstance(content, str):
            content_blocks = [{"type": "text", "text": content}]
        elif isinstance(content, list):
            content_blocks = content
        elif content is not None:
            content_blocks = [content.model_dump() if hasattr(content, "model_dump") else content]

        return cls(
            message_id=entity.id,
            created_at=entity.created_at,
            session_id=entity.session_id,
            task_id=entity.task_id,
            type=entity.type,
            role=entity.role,
            index=entity.index,
            timestamp=entity.timestamp,
            content_preview=entity.content_preview or entity.get_content_preview(),
            parent_tool_use_id=entity.parent_tool_use_id,
            status=entity.status,
            queue_position=entity.queue_position,
            content=content,
            content_blocks=content_blocks,
            tool_uses=tool_uses,
            metadata=metadata,
        )


class MessageListResponse(BaseModel):
    """訊息列表回應."""

    items: List[MessageResponse]
    total: int
    limit: int
    offset: int


class QueueMessageResponse(BaseModel):
    """佇列訊息回應."""

    success: bool = True
    message: MessageResponse


class QueueListResponse(BaseModel):
    """佇列列表回應."""

    items: List[MessageResponse]
    total: int


class BulkCreateResponse(BaseModel):
    """批次建立回應."""

    success: bool = True
    created_count: int
    messages: List[MessageResponse]


__all__ = [
    "BulkCreateResponse",
    "MessageBulkCreate",
    "MessageCreate",
    "MessageListResponse",
    "MessageMetadataResponse",
    "MessageQuery",
    "MessageResponse",
    "MessageUpdate",
    "PermissionRequestContentResponse",
    "QueueListResponse",
    "QueueMessageRequest",
    "QueueMessageResponse",
    "ToolUseCreate",
    "ToolUseResponse",
]
