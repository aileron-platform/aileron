"""Content Block Schema definitions.

Defines various ContentBlock types in Message content.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class TextBlock(BaseModel):
    """Text content block."""

    type: Literal["text"] = "text"
    text: str = ""


class ImageBlock(BaseModel):
    """Image content block (Claude supported)."""

    type: Literal["image"] = "image"
    source: Dict[str, Any] = Field(default_factory=dict)
    # source: { type: "base64", media_type: "image/png", data: "..." }


class ToolUseBlock(BaseModel):
    """Tool use block."""

    type: Literal["tool_use"] = "tool_use"
    id: str = ""
    name: str = ""
    input: Dict[str, Any] = Field(default_factory=dict)


class ToolResultBlock(BaseModel):
    """Tool result block."""

    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str = ""
    content: Union[str, Dict[str, Any], List[Dict[str, Any]]] = ""
    is_error: bool = False


class ThinkingBlock(BaseModel):
    """Thinking process block (Claude exclusive)."""

    type: Literal["thinking"] = "thinking"
    thinking: str = ""
    signature: Optional[str] = None  # Claude's thinking signature


class SystemStatusBlock(BaseModel):
    """System status block."""

    type: Literal["system_status"] = "system_status"
    status: str = ""  # e.g., "compacting", "saving", "processing"
    message: Optional[str] = None
    progress: Optional[float] = None  # 0-100


class SystemCompleteBlock(BaseModel):
    """System complete notification block."""

    type: Literal["system_complete"] = "system_complete"
    message: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ContentBlock union type
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
    """Parse ContentBlock.

    Args:
        data: Raw data

    Returns:
        Corresponding type ContentBlock
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
    """Parse multiple ContentBlocks.

    Args:
        data: Raw data list

    Returns:
        ContentBlock list
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
