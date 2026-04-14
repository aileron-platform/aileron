"""Content Block Schema 定義.

定義 Message 內容中的各種 ContentBlock 類型。
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class TextBlock(BaseModel):
    """文字內容區塊."""

    type: Literal["text"] = "text"
    text: str = ""


class ImageBlock(BaseModel):
    """影像內容區塊 (Claude 支援)."""

    type: Literal["image"] = "image"
    source: Dict[str, Any] = Field(default_factory=dict)
    # source: { type: "base64", media_type: "image/png", data: "..." }


class ToolUseBlock(BaseModel):
    """工具調用區塊."""

    type: Literal["tool_use"] = "tool_use"
    id: str = ""
    name: str = ""
    input: Dict[str, Any] = Field(default_factory=dict)


class ToolResultBlock(BaseModel):
    """工具結果區塊."""

    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str = ""
    content: Union[str, Dict[str, Any], List[Dict[str, Any]]] = ""
    is_error: bool = False


class ThinkingBlock(BaseModel):
    """思考過程區塊 (Claude 專屬)."""

    type: Literal["thinking"] = "thinking"
    thinking: str = ""
    signature: Optional[str] = None  # Claude 的思考簽名


class SystemStatusBlock(BaseModel):
    """系統狀態區塊."""

    type: Literal["system_status"] = "system_status"
    status: str = ""  # e.g., "compacting", "saving", "processing"
    message: Optional[str] = None
    progress: Optional[float] = None  # 0-100


class SystemCompleteBlock(BaseModel):
    """系統完成通知區塊."""

    type: Literal["system_complete"] = "system_complete"
    message: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ContentBlock 聯合類型
ContentBlock = Union[
    TextBlock,
    ImageBlock,
    ToolUseBlock,
    ToolResultBlock,
    ThinkingBlock,
    SystemStatusBlock,
    SystemCompleteBlock,
]


def parse_content_block(data: Dict[str, Any]) -> ContentBlock:
    """解析 ContentBlock.

    Args:
        data: 原始資料

    Returns:
        對應類型的 ContentBlock
    """
    block_type = data.get("type", "text")

    type_map = {
        "text": TextBlock,
        "image": ImageBlock,
        "tool_use": ToolUseBlock,
        "tool_result": ToolResultBlock,
        "thinking": ThinkingBlock,
        "system_status": SystemStatusBlock,
        "system_complete": SystemCompleteBlock,
    }

    block_class = type_map.get(block_type, TextBlock)
    return block_class(**data)


def parse_content_blocks(data: List[Dict[str, Any]]) -> List[ContentBlock]:
    """解析多個 ContentBlock.

    Args:
        data: 原始資料列表

    Returns:
        ContentBlock 列表
    """
    return [parse_content_block(item) for item in data]


__all__ = [
    "ContentBlock",
    "ImageBlock",
    "SystemCompleteBlock",
    "SystemStatusBlock",
    "TextBlock",
    "ThinkingBlock",
    "ToolResultBlock",
    "ToolUseBlock",
    "parse_content_block",
    "parse_content_blocks",
]
