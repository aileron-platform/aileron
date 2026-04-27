"""Domain entity definitions.

Domain entities have unique identifiers and represent core business objects in the system.
Includes:
- Session: Session entity
- Task: Task entity
- Message: Message entity
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

from .enums import (
    AgenticTool,
    AgentSessionStatus,
    ArchivedReason,
    ContentBlockType,
    MessageRole,
    MessageStatus,
    MessageType,
    TaskStatus,
)
from .value_objects import (
    MessageRange,
    ModelConfig,
    PermissionConfig,
    PermissionRequestContent,
    ToolUse,
)


@dataclass(slots=True)
class AgentSession:
    """Agent session entity.

    Represents a continuous conversation session with an AI assistant.
    Top-level container using Session-Task-Message three-layer architecture.
    """

    # Primary keys and timestamps
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: str = "anonymous"

    # State fields
    status: AgentSessionStatus = AgentSessionStatus.IDLE
    agentic_tool: AgenticTool = AgenticTool.CLAUDE_CODE
    workspace_id: str = ""
    source: str = "user"
    ready_for_prompt: bool = False
    archived: bool = False
    archived_reason: Optional[ArchivedReason] = None

    # JSON data blob fields
    agentic_tool_version: Optional[str] = None
    sdk_session_id: Optional[str] = None
    mcp_token: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    context_files: List[str] = field(default_factory=list)
    tasks: List[str] = field(default_factory=list)  # Task ID array
    message_count: int = 0

    # Configuration
    permission_config: Optional[PermissionConfig] = None
    model_settings: Optional[ModelConfig] = None

    # Context Window tracking
    current_context_usage: Optional[int] = None
    context_window_limit: Optional[int] = None
    last_context_update_at: Optional[str] = None

    # Custom context
    custom_context: Dict[str, Any] = field(default_factory=dict)

    # Callback configuration
    callback_config: Optional[Dict[str, Any]] = None

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "AgentSession":
        """Create entity from database record."""
        data = row.get("data", {}) or {}

        # Parse permission_config
        permission_config = None
        if data.get("permission_config"):
            permission_config = PermissionConfig.from_dict(data["permission_config"])

        # Parse model_settings (stored as model_config in DB)
        model_settings = None
        if data.get("model_config"):
            model_settings = ModelConfig.from_dict(data["model_config"])

        return cls(
            id=row["session_id"],
            created_at=row["created_at"],
            updated_at=row.get("updated_at"),
            created_by=row.get("created_by", "anonymous"),
            status=AgentSessionStatus(row["status"]),
            agentic_tool=AgenticTool(row["agentic_tool"]),
            workspace_id=row["workspace_id"],
            source=row.get("source", "user"),
            ready_for_prompt=row.get("ready_for_prompt", False),
            archived=row.get("archived", False),
            archived_reason=ArchivedReason(row["archived_reason"]) if row.get("archived_reason") else None,
            # Data blob fields
            agentic_tool_version=data.get("agentic_tool_version"),
            sdk_session_id=data.get("sdk_session_id"),
            mcp_token=data.get("mcp_token"),
            title=data.get("title"),
            description=data.get("description"),
            context_files=data.get("contextFiles", []),
            tasks=data.get("tasks", []),
            message_count=data.get("message_count", 0),
            permission_config=permission_config,
            model_settings=model_settings,
            current_context_usage=data.get("current_context_usage"),
            context_window_limit=data.get("context_window_limit"),
            last_context_update_at=data.get("last_context_update_at"),
            custom_context=data.get("custom_context", {}),
            callback_config=data.get("callback_config"),
        )

    def to_data_blob(self) -> Dict[str, Any]:
        """Convert to data blob dictionary."""
        data: Dict[str, Any] = {
            "contextFiles": self.context_files,
            "tasks": self.tasks,
            "message_count": self.message_count,
        }

        if self.agentic_tool_version:
            data["agentic_tool_version"] = self.agentic_tool_version
        if self.sdk_session_id:
            data["sdk_session_id"] = self.sdk_session_id
        if self.mcp_token:
            data["mcp_token"] = self.mcp_token
        if self.title:
            data["title"] = self.title
        if self.description:
            data["description"] = self.description
        if self.permission_config:
            data["permission_config"] = self.permission_config.to_dict()
        if self.model_settings:
            data["model_config"] = self.model_settings.to_dict()
        if self.current_context_usage is not None:
            data["current_context_usage"] = self.current_context_usage
        if self.context_window_limit is not None:
            data["context_window_limit"] = self.context_window_limit
        if self.last_context_update_at:
            data["last_context_update_at"] = self.last_context_update_at
        if self.custom_context:
            data["custom_context"] = self.custom_context
        if self.callback_config:
            data["callback_config"] = self.callback_config

        return data


@dataclass(slots=True)
class Task:
    """Task entity.

    Represents the lifecycle of a prompt execution, tracking state and token usage.
    """

    # Primary keys and foreign keys
    id: str
    session_id: str
    created_at: datetime
    created_by: str = "anonymous"

    # Time tracking
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # State
    status: TaskStatus = TaskStatus.CREATED

    # JSON data blob fields
    description: Optional[str] = None
    full_prompt: Optional[str] = None
    message_range: Optional[MessageRange] = None
    model: Optional[str] = None
    tool_use_count: int = 0
    duration_ms: Optional[int] = None
    agent_session_id: Optional[str] = None
    raw_sdk_response: Optional[Dict[str, Any]] = None
    computed_context_window: Optional[int] = None
    report: Optional[Dict[str, Any]] = None
    permission_request: Optional[Dict[str, Any]] = None

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Task":
        """Create entity from database record."""
        data = row.get("data", {}) or {}

        # Parse message_range
        message_range = None
        if data.get("message_range"):
            message_range = MessageRange.from_dict(data["message_range"])

        return cls(
            id=row["task_id"],
            session_id=row["session_id"],
            created_at=row["created_at"],
            created_by=row.get("created_by", "anonymous"),
            started_at=row.get("started_at"),
            completed_at=row.get("completed_at"),
            status=TaskStatus(row["status"]),
            # Data blob fields
            description=data.get("description"),
            full_prompt=data.get("full_prompt"),
            message_range=message_range,
            model=data.get("model"),
            tool_use_count=data.get("tool_use_count", 0),
            duration_ms=data.get("duration_ms"),
            agent_session_id=data.get("agent_session_id"),
            raw_sdk_response=data.get("raw_sdk_response"),
            computed_context_window=data.get("computed_context_window"),
            report=data.get("report"),
            permission_request=data.get("permission_request"),
        )

    def to_data_blob(self) -> Dict[str, Any]:
        """Convert to data blob dictionary."""
        data: Dict[str, Any] = {
            "tool_use_count": self.tool_use_count,
        }

        if self.description:
            data["description"] = self.description
        if self.full_prompt:
            data["full_prompt"] = self.full_prompt
        if self.message_range:
            data["message_range"] = self.message_range.to_dict()
        if self.model:
            data["model"] = self.model
        if self.duration_ms is not None:
            data["duration_ms"] = self.duration_ms
        if self.agent_session_id:
            data["agent_session_id"] = self.agent_session_id
        if self.raw_sdk_response:
            data["raw_sdk_response"] = self.raw_sdk_response
        if self.computed_context_window is not None:
            data["computed_context_window"] = self.computed_context_window
        if self.report:
            data["report"] = self.report
        if self.permission_request:
            data["permission_request"] = self.permission_request

        return data

    def can_transition_to(self, new_status: TaskStatus) -> bool:
        """Check if can transition to specified status."""
        # Terminal states cannot transition
        if self.status.is_terminal:
            return False

        # Define valid state transitions
        valid_transitions: Dict[TaskStatus, set[TaskStatus]] = {
            TaskStatus.CREATED: {TaskStatus.RUNNING},
            TaskStatus.RUNNING: {
                TaskStatus.AWAITING_PERMISSION,
                TaskStatus.STOPPING,
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
            },
            TaskStatus.AWAITING_PERMISSION: {
                TaskStatus.RUNNING,
                TaskStatus.STOPPING,
                TaskStatus.FAILED,
            },
            TaskStatus.STOPPING: {TaskStatus.STOPPED, TaskStatus.FAILED},
        }

        allowed = valid_transitions.get(self.status, set())
        return new_status in allowed


# ContentBlock type definition
ContentBlock = Dict[str, Any]


@dataclass(slots=True)
class Message:
    """Message entity.

    Represents a message in a conversation, supporting multiple content types.
    """

    # Primary keys and foreign keys
    id: str
    session_id: str
    task_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Message attributes
    type: MessageType = MessageType.USER
    role: MessageRole = MessageRole.USER
    index: int = 0
    timestamp: Optional[datetime] = None
    content_preview: Optional[str] = None
    parent_tool_use_id: Optional[str] = None
    status: Optional[MessageStatus] = None
    queue_position: Optional[int] = None

    # JSON data blob fields
    content: Union[str, List[ContentBlock], PermissionRequestContent, None] = None
    tool_uses: List[ToolUse] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Message":
        """Create entity from database record."""
        data = row.get("data", {}) or {}

        # Parse tool_uses
        tool_uses = []
        for tu in data.get("tool_uses", []):
            tool_uses.append(ToolUse.from_dict(tu))

        # Parse content
        content = data.get("content")
        if isinstance(content, dict) and "request_id" in content:
            content = PermissionRequestContent.from_dict(content)

        # Parse status
        status = None
        if row.get("status"):
            status = MessageStatus(row["status"])

        return cls(
            id=row["message_id"],
            session_id=row["session_id"],
            task_id=row.get("task_id"),
            created_at=row["created_at"],
            type=MessageType(row["type"]),
            role=MessageRole(row["role"]),
            index=row["index"],
            timestamp=row.get("timestamp"),
            content_preview=row.get("content_preview"),
            parent_tool_use_id=row.get("parent_tool_use_id"),
            status=status,
            queue_position=row.get("queue_position"),
            # Data blob fields
            content=content,
            tool_uses=tool_uses,
            metadata=data.get("metadata", {}),
        )

    def to_data_blob(self) -> Dict[str, Any]:
        """Convert to data blob dictionary."""
        data: Dict[str, Any] = {}

        if self.content is not None:
            if isinstance(self.content, PermissionRequestContent):
                data["content"] = self.content.to_dict()
            else:
                data["content"] = self.content

        if self.tool_uses:
            data["tool_uses"] = [tu.to_dict() for tu in self.tool_uses]

        if self.metadata:
            data["metadata"] = self.metadata

        return data

    def get_content_preview(self, max_length: int = 200) -> str:
        """Get content preview."""
        if self.content_preview:
            return self.content_preview

        if isinstance(self.content, str):
            return self.content[:max_length]

        if isinstance(self.content, list):
            # Find first text block
            for block in self.content:
                if block.get("type") == "text":
                    text = block.get("text", "")
                    return text[:max_length]

        if isinstance(self.content, PermissionRequestContent):
            return f"Permission request: {self.content.tool_name}"

        # Handle dict type (permission request as dict)
        if isinstance(self.content, dict) and "tool_name" in self.content:
            logger.warning(
                "Permission request content is dict instead of PermissionRequestContent object",
                extra={
                    "session_id": self.session_id,
                    "message_id": self.id,
                    "task_id": self.task_id,
                    "content_type": type(self.content).__name__,
                }
            )
            return f"Permission request: {self.content.get('tool_name', 'Unknown')}"

        return ""


__all__ = [
    "AgentSession",
    "ContentBlock",
    "Message",
    "Task",
]
