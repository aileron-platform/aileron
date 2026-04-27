"""Database model definitions (mapped to Workspace Manager tables)"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """SQLAlchemy Base class"""

    pass


class User(Base):
    """User table (read-only)"""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Workspace(Base):
    """Workspace table"""

    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    owner_id: Mapped[str] = mapped_column(String(128), ForeignKey("users.id"))

    # Workspace settings
    language: Mapped[Optional[str]] = mapped_column(String(10))
    timezone: Mapped[Optional[str]] = mapped_column(String(64))
    default_shell: Mapped[Optional[str]] = mapped_column(String(32))
    auto_start: Mapped[Optional[bool]] = mapped_column()
    acp_cli_args: Mapped[list[str]] = mapped_column(JSON, default=list)

    # Runtime container fields
    runtime_container_id: Mapped[Optional[str]] = mapped_column(Text)
    runtime_internal_url: Mapped[Optional[str]] = mapped_column(Text)
    runtime_external_url: Mapped[Optional[str]] = mapped_column(Text)
    runtime_internal_port: Mapped[int] = mapped_column(Integer, default=3002)
    runtime_external_port: Mapped[Optional[int]] = mapped_column(Integer)
    runtime_status: Mapped[str] = mapped_column(Text, default="stopped")
    runtime_last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AutomationJob(Base):
    """Automation job table (read-only)"""

    __tablename__ = "automation_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    creator_user_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    workspace_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    trigger: Mapped[str] = mapped_column(String(32), nullable=False)
    schedule: Mapped[str] = mapped_column(String(255), nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    notifications: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    task_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    webhook_api_key: Mapped[Optional[str]] = mapped_column(String(64))

    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_duration: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_duration: Mapped[Optional[int]] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    creator: Mapped[User] = relationship("User")
    workspace: Mapped[Workspace] = relationship("Workspace")
    executions: Mapped[list["JobExecution"]] = relationship(
        "JobExecution",
        back_populates="task",
        order_by="desc(JobExecution.started_at)",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'paused', 'failed', 'draft')",
            name="automation_jobs_status_check",
        ),
        CheckConstraint(
            "trigger IN ('cron', 'manual', 'webhook')",
            name="automation_jobs_trigger_check",
        ),
    )


class JobExecution(Base):
    """Job execution record table (read-only)"""

    __tablename__ = "job_executions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("automation_jobs.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[Optional[str]] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    trigger: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration: Mapped[Optional[int]] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    execution_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    task: Mapped[AutomationJob] = relationship("AutomationJob", back_populates="executions")

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'success', 'failed')",
            name="job_executions_status_check",
        ),
    )


__all__ = [
    "Base",
    "User",
    "Workspace",
    "AutomationJob",
    "JobExecution",
]
