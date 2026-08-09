from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models import Base

JsonbType = JSONB().with_variant(JSON(), "sqlite")


class ThreadModel(Base):
    """Thread table."""

    __tablename__ = "threads"
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    origin: Mapped[str] = mapped_column(
        String(16), default="user", index=True, nullable=False
    )
    automation_job_id: Mapped[str | None] = mapped_column(String(36), index=True)
    automation_execution_id: Mapped[str | None] = mapped_column(
        String(36), unique=True, index=True
    )
    title: Mapped[str] = mapped_column(Text, default="", nullable=False)
    agentic_tool: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    claude_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    version: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    queued_messages: Mapped[list[dict[str, Any]]] = mapped_column(
        JsonbType,
        default=list,
        nullable=False,
    )
    draft_message: Mapped[dict[str, Any] | None] = mapped_column(
        JsonbType, nullable=True
    )
    active_turn_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "thread_turns.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_threads_active_turn",
        ),
        nullable=True,
    )
    active_turn_execution_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey(
            "thread_turn_executions.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_threads_active_turn_execution",
        ),
        nullable=True,
    )
    git_context_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    context_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    context_window: Mapped[int | None] = mapped_column(Integer, nullable=True)
    archived: Mapped[bool] = mapped_column(
        Boolean, default=False, index=True, nullable=False
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_info: Mapped[dict[str, Any] | None] = mapped_column(JsonbType, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ThreadMessageModel(Base):
    """Append-only conversation log."""

    __tablename__ = "thread_messages"

    __table_args__ = (
        UniqueConstraint(
            "thread_id", "message_sequence", name="uq_thread_messages_sequence"
        ),
        UniqueConstraint(
            "turn_execution_id",
            "tool_call_key",
            name="uq_thread_messages_execution_tool_call",
        ),
        UniqueConstraint(
            "turn_execution_id",
            "source_event_key",
            name="uq_thread_messages_execution_source_event",
        ),
        Index("ix_thread_messages_turn_sequence", "turn_id", "message_sequence"),
        Index(
            "ix_thread_messages_execution_sequence",
            "turn_execution_id",
            "message_sequence",
        ),
        CheckConstraint(
            "(type = 'tool_result' AND result_kind IN "
            "('provider_result', 'interaction_answer')) OR "
            "(type <> 'tool_result' AND result_kind IS NULL)",
            name="ck_thread_messages_result_kind",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    thread_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    turn_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("thread_turns.id", ondelete="CASCADE"), nullable=False
    )
    turn_execution_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("thread_turn_executions.id", ondelete="CASCADE"),
        nullable=False,
    )
    message_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    parent_tool_use_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("thread_messages.id", ondelete="CASCADE"),
        nullable=True,
    )
    tool_call_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_event_key: Mapped[str] = mapped_column(String(255), nullable=False)
    result_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    content: Mapped[dict[str, Any]] = mapped_column(JsonbType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ThreadTurnModel(Base):
    """Logical user intent lifecycle boundary."""

    __tablename__ = "thread_turns"
    __table_args__ = (
        UniqueConstraint("thread_id", "sequence", name="uq_thread_turns_sequence"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    thread_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("threads.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(BigInteger, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_info: Mapped[dict[str, Any] | None] = mapped_column(JsonbType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


Index(
    "ix_thread_turns_thread_sequence_desc",
    ThreadTurnModel.thread_id,
    ThreadTurnModel.sequence.desc(),
)


TIMELINE_ANCHOR_TYPES = (
    "user",
    "agent_text",
    "thinking",
    "tool_call",
    "system",
    "system_init",
    "git_diff",
    "error",
)


Index(
    "ix_thread_messages_timeline_anchors",
    ThreadMessageModel.thread_id,
    ThreadMessageModel.message_sequence.desc(),
    postgresql_where=ThreadMessageModel.type.in_(TIMELINE_ANCHOR_TYPES),
    sqlite_where=ThreadMessageModel.type.in_(TIMELINE_ANCHOR_TYPES),
)


Index(
    "uq_thread_messages_tool_result_kind",
    ThreadMessageModel.parent_tool_use_id,
    ThreadMessageModel.result_kind,
    unique=True,
    postgresql_where=ThreadMessageModel.type == "tool_result",
    sqlite_where=ThreadMessageModel.type == "tool_result",
)


class ThreadTurnExecutionModel(Base):
    """One provider runner invocation within a logical turn."""

    __tablename__ = "thread_turn_executions"
    __table_args__ = (
        UniqueConstraint(
            "turn_id", "sequence", name="uq_thread_turn_executions_sequence"
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    turn_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("thread_turns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    agentic_tool: Mapped[str] = mapped_column(String(32), nullable=False)
    agent_resume_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    version: Mapped[int] = mapped_column(BigInteger, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_info: Mapped[dict[str, Any] | None] = mapped_column(JsonbType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ThreadToolResultContentModel(Base):
    """Full serialized payload for a tool result message."""

    __tablename__ = "thread_tool_result_contents"

    message_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("thread_messages.id", ondelete="CASCADE"),
        primary_key=True,
    )
    media_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    byte_length: Mapped[int] = mapped_column(BigInteger, nullable=False)
    line_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
