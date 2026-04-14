"""SQLAlchemy ORM 模型定義"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Union

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class User(Base):
    """使用者資料表"""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    keycloak_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    settings: Mapped[Optional["UserSetting"]] = relationship(
        "UserSetting", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    workspaces: Mapped[list["Workspace"]] = relationship(
        "Workspace", back_populates="owner", cascade="all, delete-orphan"
    )


class UserSetting(Base):
    """使用者設定"""

    __tablename__ = "user_settings"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )

    claude_auth_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    claude_selected_model: Mapped[str] = mapped_column(String(64), default="claude-sonnet-4")
    claude_selected_provider: Mapped[str] = mapped_column(String(32), default="anthropic")

    git_user_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    git_user_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    git_signing_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    ssh_private_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ssh_public_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ssh_fingerprint: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    ssh_last_rotated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    general_settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    additional_settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped[User] = relationship("User", back_populates="settings")


class ModelConfig(Base):
    """可用的 Claude 模型設定"""

    __tablename__ = "model_configs"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    model_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    anthropic_model_id: Mapped[Optional[str]] = mapped_column(String(255))
    aws_bedrock_model_id: Mapped[Optional[str]] = mapped_column(String(255))
    gcp_vertex_model_id: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Workspace(Base):
    """開發工作區"""

    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    git_url: Mapped[Optional[str]] = mapped_column(Text)
    branch: Mapped[str] = mapped_column(Text, default="main")
    runtime: Mapped[str] = mapped_column(Text, default="universal")  # 對應 container_images.yaml 中的 default_image
    provisioner: Mapped[str] = mapped_column(Text, default="docker")
    target_namespace: Mapped[Optional[str]] = mapped_column(Text)
    env_vars: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    runtime_resources: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    setup_script: Mapped[Optional[str]] = mapped_column(Text)

    runtime_container_id: Mapped[Optional[str]] = mapped_column(Text)
    runtime_internal_url: Mapped[Optional[str]] = mapped_column(Text)
    runtime_external_url: Mapped[Optional[str]] = mapped_column(Text)
    runtime_internal_port: Mapped[int] = mapped_column(Integer, default=3002)
    runtime_external_port: Mapped[Optional[int]] = mapped_column(Integer)
    runtime_status: Mapped[str] = mapped_column(Text, default="stopped")
    runtime_last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    web_preview_internal_port: Mapped[int] = mapped_column(Integer, default=3003)
    web_preview_external_port: Mapped[Optional[int]] = mapped_column(Integer)
    web_preview_internal_url: Mapped[Optional[str]] = mapped_column(Text)
    web_preview_external_url: Mapped[Optional[str]] = mapped_column(Text)

    terminal_external_port: Mapped[Optional[int]] = mapped_column(Integer)
    terminal_external_url: Mapped[Optional[str]] = mapped_column(Text)

    workspace_firewall_network_access_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    workspace_firewall_domain_access_mode: Mapped[str] = mapped_column(Text, default="all")
    workspace_firewall_allowed_domains: Mapped[list[str]] = mapped_column(JSON, default=list)
    browser_firewall_network_access_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    browser_firewall_domain_access_mode: Mapped[str] = mapped_column(Text, default="all")
    browser_firewall_allowed_domains: Mapped[list[str]] = mapped_column(JSON, default=list)

    port_mappings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    active_claude_session_id: Mapped[Optional[str]] = mapped_column(Text)
    preferred_cli: Mapped[str] = mapped_column(Text, default="claude-code")
    cli_type: Mapped[str] = mapped_column(String(32), default="claude-code")
    fallback_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    workspace_path: Mapped[str] = mapped_column(Text, default="/workspace")
    acp_cli_args: Mapped[list[str]] = mapped_column(JSON, default=list)

    # Browser container fields
    browser_container_id: Mapped[Optional[str]] = mapped_column(Text)
    browser_status: Mapped[str] = mapped_column(Text, default="stopped")
    browser_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    browser_last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Browser WebRTC (neko) fields
    browser_webrtc_internal_url: Mapped[Optional[str]] = mapped_column(Text)
    browser_webrtc_external_url: Mapped[Optional[str]] = mapped_column(Text)
    browser_webrtc_internal_port: Mapped[int] = mapped_column(Integer, default=6080)
    browser_webrtc_external_port: Mapped[Optional[int]] = mapped_column(Integer)

    # Browser CDP fields
    browser_cdp_internal_port: Mapped[int] = mapped_column(Integer, default=9223)
    browser_cdp_external_port: Mapped[Optional[int]] = mapped_column(Integer)

    # Next.js container fields
    nextjs_container_id: Mapped[Optional[str]] = mapped_column(Text)
    nextjs_status: Mapped[str] = mapped_column(Text, default="stopped")
    nextjs_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    nextjs_last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Next.js URL/port fields
    nextjs_internal_url: Mapped[Optional[str]] = mapped_column(Text)
    nextjs_external_url: Mapped[Optional[str]] = mapped_column(Text)
    nextjs_internal_port: Mapped[int] = mapped_column(Integer, default=3003)
    nextjs_external_port: Mapped[Optional[int]] = mapped_column(Integer)

    # Next.js management API port
    nextjs_api_internal_port: Mapped[int] = mapped_column(Integer, default=3013)
    nextjs_api_external_port: Mapped[Optional[int]] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    owner: Mapped[User] = relationship("User", back_populates="workspaces")
    runtime_logs: Mapped[list["WorkspaceRuntimeLog"]] = relationship(
        "WorkspaceRuntimeLog",
        back_populates="workspace",
        cascade="all, delete-orphan",
        order_by="desc(WorkspaceRuntimeLog.created_at)",
    )
    runtime_jobs: Mapped[list["WorkspaceRuntimeJob"]] = relationship(
        "WorkspaceRuntimeJob",
        back_populates="workspace",
        cascade="all, delete-orphan",
        order_by="desc(WorkspaceRuntimeJob.scheduled_at)",
    )

    __table_args__ = (
        CheckConstraint(
            "runtime_status IN ('stopped', 'starting', 'running', 'error', 'deleting', 'restarting')",
            name="workspaces_runtime_status_check",
        ),
        CheckConstraint(
            "provisioner IN ('docker', 'kubernetes')",
            name="workspaces_provisioner_check",
        ),
        CheckConstraint(
            "workspace_firewall_domain_access_mode IN ('all', 'specific')",
            name="workspaces_workspace_firewall_domain_access_mode_check",
        ),
        CheckConstraint(
            "browser_firewall_domain_access_mode IN ('all', 'specific')",
            name="workspaces_browser_firewall_domain_access_mode_check",
        ),
        CheckConstraint(
            "browser_status IN ('stopped', 'starting', 'running', 'error', 'restarting')",
            name="workspaces_browser_status_check",
        ),
        CheckConstraint(
            "nextjs_status IN ('stopped', 'starting', 'running', 'error', 'restarting')",
            name="workspaces_nextjs_status_check",
        ),
    )


class WorkspaceRuntimeLog(Base):
    """工作區 Runtime 佈建日誌"""

    __tablename__ = "workspace_runtime_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    log_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    workspace: Mapped[Workspace] = relationship("Workspace", back_populates="runtime_logs")


class WorkspaceRuntimeJob(Base):
    """工作區 Runtime 背景任務排程"""

    __tablename__ = "workspace_runtime_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    operation: Mapped[str] = mapped_column(String(32), nullable=False)
    strategy: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    workspace: Mapped[Workspace] = relationship("Workspace", back_populates="runtime_jobs")


class AutomationJob(Base):
    """自動化任務資料表"""

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

    # 佇列配置欄位
    max_queue_size: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    queue_timeout: Mapped[int] = mapped_column(Integer, default=3600, nullable=False)

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
        back_populates="job",
        cascade="all, delete-orphan",
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
    """任務執行紀錄資料表"""

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

    # 佇列相關欄位
    queue_position: Mapped[Optional[int]] = mapped_column(Integer)
    queued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    job: Mapped[AutomationJob] = relationship("AutomationJob", back_populates="executions")

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'waiting', 'running', 'success', 'failed', 'cancelled', 'timeout')",
            name="job_executions_status_check",
        ),
    )


class TemplateCategory(Base):
    """模板分類資料表"""

    __tablename__ = "template_categories"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    icon: Mapped[Optional[str]] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Template(Base):
    """模板中心資料表"""

    __tablename__ = "templates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    author_name: Mapped[str] = mapped_column("developer", String(255), nullable=False)
    author_email: Mapped[Optional[str]] = mapped_column(String(255))
    author_url: Mapped[Optional[str]] = mapped_column(String(255))
    category: Mapped[Optional[str]] = mapped_column(String(100))
    keywords: Mapped[list[str]] = mapped_column("tags", JSON, default=list)
    version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)
    cli_type: Mapped[str] = mapped_column(String(32), default="claude-code", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    readme_content: Mapped[Optional[str]] = mapped_column(Text)
    init_commands: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "cli_type IN ('claude-code', 'codex', 'gemini')",
            name="templates_cli_type_check",
        ),
        CheckConstraint(
            "status IN ('draft', 'released')",
            name="templates_status_check",
        ),
    )


class TemplateFeature(Base):
    """模板功能資料表"""

    __tablename__ = "template_features"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    feature_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    feature_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    icon: Mapped[Optional[str]] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


class TemplateFeatureCliType(Base):
    """模板功能 CLI 類型關聯表"""

    __tablename__ = "template_feature_cli_types"

    feature_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("template_features.id", ondelete="CASCADE"), primary_key=True
    )
    cli_type: Mapped[str] = mapped_column(String(32), primary_key=True)


class TemplateFeatureMapping(Base):
    """模板功能映射表"""

    __tablename__ = "template_feature_mappings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    feature_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("template_features.id", ondelete="CASCADE"), nullable=False
    )
    template_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("templates.id", ondelete="CASCADE"), nullable=False
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    indexed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
