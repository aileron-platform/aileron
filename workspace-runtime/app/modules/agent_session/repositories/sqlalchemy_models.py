"""SQLAlchemy ORM 模型定義.

定義 Agent Session 系統的資料庫表結構，採用 Materialized Columns + JSON Blob 混合模式。

表結構：
- agent_sessions: 會話表
- agent_tasks: 任務表
- agent_messages: 訊息表
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative 基底類別."""

    pass


class AgentSessionModel(Base):
    """會話 ORM 模型.

    Materialized Columns (用於查詢):
    - session_id, created_at, updated_at, created_by
    - status, agentic_tool, workspace_id
    - ready_for_prompt, archived, archived_reason

    JSON Data Blob:
    - permission_config, model_config, context tracking
    - tasks array, custom_context
    """

    __tablename__ = "agent_sessions"

    # 主鍵
    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # 時間戳
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

    # 建立者
    created_by: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        default="anonymous",
    )

    # 狀態欄位
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

    # 來源（user / automation）
    source: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="user",
        index=True,
    )

    # 布林欄位
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

    # 索引
    __table_args__ = (
        Index("agent_sessions_workspace_status_idx", "workspace_id", "status"),
        Index("agent_sessions_created_idx", "created_at"),
    )


class AgentTaskModel(Base):
    """任務 ORM 模型.

    Materialized Columns:
    - task_id, session_id, created_at, started_at, completed_at
    - status, created_by

    JSON Data Blob:
    - description, full_prompt, message_range
    - raw_sdk_response, computed_context_window
    - permission_request
    """

    __tablename__ = "agent_tasks"

    # 主鍵
    task_id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # 外鍵
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agent_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 時間戳
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

    # 狀態
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="created",
        index=True,
    )

    # 建立者
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

    # 索引
    __table_args__ = (
        Index("agent_tasks_session_status_idx", "session_id", "status"),
        Index("agent_tasks_created_idx", "created_at"),
    )


class AgentMessageModel(Base):
    """訊息 ORM 模型.

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

    # 主鍵
    message_id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # 時間戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # 外鍵
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

    # 訊息屬性
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

    # 內容預覽 (前 200 字)
    content_preview: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # 巢狀工具支援
    parent_tool_use_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )

    # 佇列支援
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

    # 索引
    __table_args__ = (
        Index("agent_messages_session_index_idx", "session_id", "index"),
        Index("agent_messages_task_idx", "task_id"),
        Index("agent_messages_queue_idx", "session_id", "status", "queue_position"),
        # 用於權限請求查詢優化
        Index("agent_messages_session_type_idx", "session_id", "type"),
    )


__all__ = [
    "AgentMessageModel",
    "AgentSessionModel",
    "AgentTaskModel",
    "Base",
]
