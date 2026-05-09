"""SQLAlchemy ORM model definitions"""

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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class User(Base):
    """UserTable"""

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
    workspace_shares_received: Mapped[list["WorkspaceShare"]] = relationship(
        "WorkspaceShare",
        back_populates="shared_with_user",
        cascade="all, delete-orphan",
        foreign_keys="WorkspaceShare.shared_with_user_id",
    )
    workspace_shares_granted: Mapped[list["WorkspaceShare"]] = relationship(
        "WorkspaceShare",
        back_populates="granted_by_user",
        foreign_keys="WorkspaceShare.granted_by_user_id",
    )
    knowledge_bases_owned: Mapped[list["KnowledgeBase"]] = relationship(
        "KnowledgeBase",
        back_populates="owner",
        cascade="all, delete-orphan",
        foreign_keys="KnowledgeBase.owner_id",
    )
    knowledge_base_shares_received: Mapped[list["KnowledgeBaseShare"]] = relationship(
        "KnowledgeBaseShare",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="KnowledgeBaseShare.user_id",
    )
    knowledge_base_shares_granted: Mapped[list["KnowledgeBaseShare"]] = relationship(
        "KnowledgeBaseShare",
        back_populates="granted_by",
        foreign_keys="KnowledgeBaseShare.granted_by_id",
    )
    knowledge_base_attachments: Mapped[list["WorkspaceKnowledgeBaseAttachment"]] = relationship(
        "WorkspaceKnowledgeBaseAttachment",
        back_populates="attached_by",
        foreign_keys="WorkspaceKnowledgeBaseAttachment.attached_by_id",
    )


class UserSetting(Base):
    """UserSettings"""

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
    """Available Claude model settings"""

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
    """Development workspace"""

    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    git_url: Mapped[Optional[str]] = mapped_column(Text)
    branch: Mapped[str] = mapped_column(Text, default="main")
    runtime: Mapped[str] = mapped_column(Text, default="universal")  # Corresponds to default_image in container_images.yaml
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

    canvas_container_id: Mapped[Optional[str]] = mapped_column(Text)
    canvas_status: Mapped[str] = mapped_column(Text, default="stopped")
    canvas_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    canvas_last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    canvas_internal_url: Mapped[Optional[str]] = mapped_column(Text)
    canvas_external_url: Mapped[Optional[str]] = mapped_column(Text)
    canvas_internal_port: Mapped[int] = mapped_column(Integer, default=3003)
    canvas_external_port: Mapped[Optional[int]] = mapped_column(Integer)
    canvas_api_internal_port: Mapped[int] = mapped_column(Integer, default=3013)
    canvas_api_external_port: Mapped[Optional[int]] = mapped_column(Integer)
    canvas_type: Mapped[str] = mapped_column(Text, default="default")
    canvas_manifest_status: Mapped[str] = mapped_column(Text, default="missing")
    canvas_last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    canvas_last_reset_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    terminal_external_port: Mapped[Optional[int]] = mapped_column(Integer)
    terminal_external_url: Mapped[Optional[str]] = mapped_column(Text)

    workspace_firewall_network_access_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    workspace_firewall_domain_access_mode: Mapped[str] = mapped_column(Text, default="all")
    workspace_firewall_allowed_domains: Mapped[list[str]] = mapped_column(JSON, default=list)
    browser_firewall_network_access_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    browser_firewall_domain_access_mode: Mapped[str] = mapped_column(Text, default="all")
    browser_firewall_allowed_domains: Mapped[list[str]] = mapped_column(JSON, default=list)

    active_claude_session_id: Mapped[Optional[str]] = mapped_column(Text)
    preferred_cli: Mapped[str] = mapped_column(Text, default="claude-code")
    cli_type: Mapped[str] = mapped_column(String(32), default="claude-code")
    fallback_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    workspace_path: Mapped[str] = mapped_column(Text, default="/workspace")
    acp_cli_args: Mapped[list[str]] = mapped_column(JSON, default=list)
    runtime_mounted_kb_signature: Mapped[Optional[str]] = mapped_column(Text)

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
    shares: Mapped[list["WorkspaceShare"]] = relationship(
        "WorkspaceShare",
        back_populates="workspace",
        cascade="all, delete-orphan",
        order_by="asc(WorkspaceShare.created_at)",
    )
    knowledge_base_attachments: Mapped[list["WorkspaceKnowledgeBaseAttachment"]] = relationship(
        "WorkspaceKnowledgeBaseAttachment",
        back_populates="workspace",
        cascade="all, delete-orphan",
        order_by="asc(WorkspaceKnowledgeBaseAttachment.created_at)",
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
            "canvas_status IN ('stopped', 'starting', 'running', 'error', 'restarting')",
            name="workspaces_canvas_status_check",
        ),
        CheckConstraint(
            "canvas_type IN ('html', 'nextjs', 'default')",
            name="workspaces_canvas_type_check",
        ),
        CheckConstraint(
            "canvas_manifest_status IN ('missing', 'valid', 'invalid')",
            name="workspaces_canvas_manifest_status_check",
        ),
    )


class WorkspaceShare(Base):
    """Workspace share authorization"""

    __tablename__ = "workspace_shares"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    shared_with_user_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    granted_by_user_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    workspace: Mapped[Workspace] = relationship("Workspace", back_populates="shares")
    shared_with_user: Mapped[User] = relationship(
        "User",
        back_populates="workspace_shares_received",
        foreign_keys=[shared_with_user_id],
    )
    granted_by_user: Mapped[User] = relationship(
        "User",
        back_populates="workspace_shares_granted",
        foreign_keys=[granted_by_user_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "shared_with_user_id",
            name="workspace_shares_workspace_user_unique",
        ),
        CheckConstraint(
            "role IN ('viewer', 'editor', 'manager')",
            name="workspace_shares_role_check",
        ),
    )


class KnowledgeBase(Base):
    """Knowledge base table"""

    __tablename__ = "knowledge_bases"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    template_id: Mapped[str] = mapped_column(String(64), nullable=False, default="general")
    owner_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    current_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quota_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    version_control_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    git_lfs_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    git_default_branch: Mapped[str] = mapped_column(String(255), nullable=False, default="main")
    git_last_commit_sha: Mapped[Optional[str]] = mapped_column(String(64))
    wiki_initialized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_indexed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_index_status: Mapped[Optional[str]] = mapped_column(String(32))
    last_index_error: Mapped[Optional[str]] = mapped_column(Text)
    tombstoned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    owner: Mapped[User] = relationship(
        "User",
        back_populates="knowledge_bases_owned",
        foreign_keys=[owner_id],
    )
    shares: Mapped[list["KnowledgeBaseShare"]] = relationship(
        "KnowledgeBaseShare",
        back_populates="knowledge_base",
        cascade="all, delete-orphan",
        order_by="asc(KnowledgeBaseShare.created_at)",
    )
    attachments: Mapped[list["WorkspaceKnowledgeBaseAttachment"]] = relationship(
        "WorkspaceKnowledgeBaseAttachment",
        back_populates="knowledge_base",
        passive_deletes=True,
        order_by="asc(WorkspaceKnowledgeBaseAttachment.created_at)",
    )

    __table_args__ = (
        UniqueConstraint("owner_id", "slug", name="knowledge_bases_owner_slug_unique"),
    )


class KnowledgeBaseShare(Base):
    """Knowledge base share authorization"""

    __tablename__ = "knowledge_base_shares"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kb_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    granted_by_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    knowledge_base: Mapped[KnowledgeBase] = relationship(
        "KnowledgeBase",
        back_populates="shares",
    )
    user: Mapped[User] = relationship(
        "User",
        back_populates="knowledge_base_shares_received",
        foreign_keys=[user_id],
    )
    granted_by: Mapped[User] = relationship(
        "User",
        back_populates="knowledge_base_shares_granted",
        foreign_keys=[granted_by_id],
    )

    __table_args__ = (
        UniqueConstraint("kb_id", "user_id", name="knowledge_base_shares_kb_user_unique"),
        CheckConstraint(
            "role IN ('viewer', 'editor', 'manager')",
            name="knowledge_base_shares_role_check",
        ),
    )


class WorkspaceKnowledgeBaseAttachment(Base):
    """Workspace and knowledge base attachment relationship"""

    __tablename__ = "workspace_knowledge_base_attachments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    kb_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("knowledge_bases.id", ondelete="RESTRICT"), nullable=False
    )
    mount_alias: Mapped[str] = mapped_column(String(255), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    attached_by_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    workspace: Mapped[Workspace] = relationship(
        "Workspace",
        back_populates="knowledge_base_attachments",
    )
    knowledge_base: Mapped[KnowledgeBase] = relationship(
        "KnowledgeBase",
        back_populates="attachments",
    )
    attached_by: Mapped[User] = relationship(
        "User",
        back_populates="knowledge_base_attachments",
        foreign_keys=[attached_by_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "kb_id",
            name="workspace_kb_attachments_workspace_kb_unique",
        ),
        UniqueConstraint(
            "workspace_id",
            "mount_alias",
            name="workspace_kb_attachments_workspace_alias_unique",
        ),
        CheckConstraint(
            "mode IN ('rw', 'ro')",
            name="workspace_kb_attachments_mode_check",
        ),
    )


class WorkspaceRuntimeLog(Base):
    """Workspace runtime provisioning log"""

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
    """Workspace runtime background task schedule"""

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
    """Automation taskTable"""

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

    # Queue configuration columns
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
    """Task execution record table"""

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

    # Queue-related columns
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
