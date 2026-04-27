"""SQLAlchemy ORM model definitions.

Defines database table structure for Agent Session system, using Materialized Columns + JSON Blob hybrid pattern.

Table structure:
- agent_sessions: Session table
- agent_tasks: Task table
- agent_messages: Message table
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base class."""

    pass


class AgentSessionModel(Base):
    """Session ORM model.

    Materialized Columns (for queries):
    - session_id, created_at, updated_at, created_by
    - status, agentic_tool, workspace_id
    - ready_for_prompt, archived, archived_reason

    JSON Data Blob:
    - permission_config, model_config, context tracking
    - tasks array, custom_context
    """

    __tablename__ = "agent_sessions"

    # Primary key
    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )

    # Creator
    created_by: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        default="anonymous",
    )

    # Status fields
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="idle",
        index=True,
    )
    agentic_tool: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="claude-code",
        index=True,
    )
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    # Source (user / automation)
    source: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="user",
        index=True,
    )

    # Boolean fields
    ready_for_prompt: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    archived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    archived_reason: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
    )

    # JSON data blob (stored as TEXT to avoid PostgreSQL JSONB limitations)
    data: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        default=None,
    )

    # Relationships
    tasks: Mapped[list["AgentTaskModel"]] = relationship(
        "AgentTaskModel",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AgentTaskModel.created_at",
    )
    messages: Mapped[list["AgentMessageModel"]] = relationship(
        "AgentMessageModel",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AgentMessageModel.index",
    )

    # Indexes
    __table_args__ = (
        Index("agent_sessions_workspace_status_idx", "workspace_id", "status"),
        Index("agent_sessions_created_idx", "created_at"),
    )


class AgentTaskModel(Base):
    """Task ORM model.

    Materialized Columns:
    - task_id, session_id, created_at, started_at, completed_at
    - status, created_by

    JSON Data Blob:
    - description, full_prompt, message_range
    - raw_sdk_response, computed_context_window
    - permission_request
    """

    __tablename__ = "agent_tasks"

    # Primary key
    task_id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Foreign key
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agent_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="created",
        index=True,
    )

    # Creator
    created_by: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        default="anonymous",
    )

    # JSON data blob (stored as TEXT to avoid PostgreSQL JSONB limitations)
    data: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        default=None,
    )

    # Relationships
    session: Mapped["AgentSessionModel"] = relationship(
        "AgentSessionModel",
        back_populates="tasks",
    )
    messages: Mapped[list["AgentMessageModel"]] = relationship(
        "AgentMessageModel",
        back_populates="task",
        order_by="AgentMessageModel.index",
    )

    # Indexes
    __table_args__ = (
        Index("agent_tasks_session_status_idx", "session_id", "status"),
        Index("agent_tasks_created_idx", "created_at"),
    )


class AgentMessageModel(Base):
    """Message ORM model.

    Materialized Columns:
    - message_id, created_at, session_id, task_id
    - type, role, index, timestamp
    - content_preview, parent_tool_use_id
    - status, queue_position

    JSON Data Blob:
    - content (string | ContentBlock[] | PermissionRequestContent)
    - tool_uses, metadata
    """

    __tablename__ = "agent_messages"

    # Primary key
    message_id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Foreign keys
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agent_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("agent_tasks.task_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Message properties
    type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="user",
    )
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="user",
    )
    index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Content preview (first 200 chars)
    content_preview: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Nested tool support
    parent_tool_use_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )

    # Queue support
    status: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
    )
    queue_position: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # JSON data blob (stored as TEXT to avoid PostgreSQL JSONB limitations)
    data: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        default=None,
    )

    # Relationships
    session: Mapped["AgentSessionModel"] = relationship(
        "AgentSessionModel",
        back_populates="messages",
    )
    task: Mapped[Optional["AgentTaskModel"]] = relationship(
        "AgentTaskModel",
        back_populates="messages",
    )

    # Indexes
    __table_args__ = (
        Index("agent_messages_session_index_idx", "session_id", "index"),
        Index("agent_messages_task_idx", "task_id"),
        Index("agent_messages_queue_idx", "session_id", "status", "queue_position"),
        # For permission request query optimization
        Index("agent_messages_session_type_idx", "session_id", "type"),
    )


__all__ = [
    "AgentMessageModel",
    "AgentSessionModel",
    "AgentTaskModel",
    "Base",
]
