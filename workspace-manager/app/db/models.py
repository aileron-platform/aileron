"""SQLAlchemy ORM model definitions"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.model_registry import get_global_model_config
from app.db.database import Base


class User(Base):
    """UserTable"""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    oidc_issuer: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    oidc_subject: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    identity_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    sync_status: Mapped[str] = mapped_column(
        String(64), default="synced", nullable=False
    )
    platform_role: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    role_status: Mapped[str] = mapped_column(
        String(64), default="missing", nullable=False
    )
    role_issues: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        server_default=text("'[]'"),
        nullable=False,
    )
    recent_workspace_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    settings: Mapped[Optional["UserSetting"]] = relationship(
        "UserSetting",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    workspaces: Mapped[list["Workspace"]] = relationship(
        "Workspace", back_populates="owner", cascade="all, delete-orphan"
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
    knowledge_base_shares_granted: Mapped[list["KnowledgeBaseShare"]] = relationship(
        "KnowledgeBaseShare",
        back_populates="granted_by",
        foreign_keys="KnowledgeBaseShare.granted_by_id",
    )
    knowledge_base_attachments: Mapped[list["WorkspaceKnowledgeBaseAttachment"]] = (
        relationship(
            "WorkspaceKnowledgeBaseAttachment",
            back_populates="attached_by",
            foreign_keys="WorkspaceKnowledgeBaseAttachment.attached_by_id",
        )
    )

    __table_args__ = (
        UniqueConstraint(
            "oidc_issuer",
            "oidc_subject",
            name="uq_users_oidc_principal",
        ),
        CheckConstraint(
            "sync_status IN ('synced', 'local_shadow_imported', 'local_shadow_missing', 'identity_sync_failed')",
            name="users_sync_status_check",
        ),
        CheckConstraint(
            "platform_role IS NULL OR platform_role IN ('admin', 'member')",
            name="users_platform_role_check",
        ),
        CheckConstraint(
            "role_status IN ('valid', 'missing', 'multiple')",
            name="users_role_status_check",
        ),
    )


class ManagerSession(Base):
    """Server-side browser session referenced by an opaque cookie handle."""

    __tablename__ = "manager_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    handle_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    oidc_issuer: Mapped[str] = mapped_column(String(2048), nullable=False)
    oidc_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    authentication_context: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    idle_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    absolute_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        Index("ix_manager_sessions_user_id", "user_id"),
        Index("ix_manager_sessions_absolute_expires_at", "absolute_expires_at"),
    )


class OIDCLoginAttempt(Base):
    """Short-lived server-owned state for an OIDC authorization-code flow."""

    __tablename__ = "oidc_login_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    state_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    code_verifier: Mapped[str] = mapped_column(String(128), nullable=False)
    nonce: Mapped[str] = mapped_column(String(128), nullable=False)
    return_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    attempt_bucket_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        Index("ix_oidc_login_attempts_expires_at", "expires_at"),
        Index(
            "ix_oidc_login_attempts_bucket_created_at",
            "attempt_bucket_hash",
            "created_at",
        ),
    )


class UserSetting(Base):
    """UserSettings"""

    __tablename__ = "user_settings"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )

    claude_auth_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    claude_selected_model: Mapped[str] = mapped_column(
        String(64),
        default=get_global_model_config("claude").default_model,
    )

    git_user_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    git_user_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    git_signing_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    ssh_private_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ssh_public_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ssh_fingerprint: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    ssh_last_rotated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    general_settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    additional_settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped[User] = relationship("User", back_populates="settings")


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
    runtime: Mapped[str] = mapped_column(
        Text, default="universal"
    )  # Corresponds to default_image in container_images.yaml
    provisioner: Mapped[str] = mapped_column(Text, default="docker", nullable=False)
    target_namespace: Mapped[Optional[str]] = mapped_column(String(253))
    env_vars: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    setup_script: Mapped[Optional[str]] = mapped_column(Text)

    bootstrap_revision: Mapped[int] = mapped_column(
        BigInteger, default=1, nullable=False
    )
    bootstrap_observed_revision: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )
    bootstrap_status: Mapped[str] = mapped_column(
        String(32), default="pending", nullable=False
    )
    bootstrap_error_code: Mapped[Optional[str]] = mapped_column(String(64))
    bootstrap_last_transition_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    runtime_container_id: Mapped[Optional[str]] = mapped_column(Text)
    runtime_desired_state: Mapped[str] = mapped_column(
        String(16), default="stopped", nullable=False
    )
    runtime_desired_revision: Mapped[int] = mapped_column(
        BigInteger, default=1, nullable=False
    )
    runtime_observed_revision: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )
    runtime_reason: Mapped[Optional[str]] = mapped_column(String(64))
    runtime_error_code: Mapped[Optional[str]] = mapped_column(String(64))
    runtime_last_transition_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    runtime_internal_url: Mapped[Optional[str]] = mapped_column(Text)
    runtime_internal_port: Mapped[int] = mapped_column(Integer, default=3002)
    runtime_status: Mapped[str] = mapped_column(Text, default="stopped", nullable=False)
    runtime_last_seen: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    knowledge_base_mount_active_revision: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )
    knowledge_base_mount_desired_revision: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )
    knowledge_base_mount_observed_revision: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )
    knowledge_base_mount_sync_status: Mapped[str] = mapped_column(
        String(32), default="ready", nullable=False
    )
    knowledge_base_mount_error_code: Mapped[Optional[str]] = mapped_column(String(64))
    knowledge_base_mount_active_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    knowledge_base_mount_candidate_snapshot: Mapped[Optional[list[dict[str, Any]]]] = (
        mapped_column(JSON)
    )
    knowledge_base_mount_failed_snapshot: Mapped[Optional[list[dict[str, Any]]]] = (
        mapped_column(JSON)
    )
    runtime_access_revision: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )
    runtime_access_observed_revision: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )
    runtime_instance_id: Mapped[Optional[str]] = mapped_column(Uuid(as_uuid=False))
    browser_instance_id: Mapped[Optional[str]] = mapped_column(Uuid(as_uuid=False))
    canvas_instance_id: Mapped[Optional[str]] = mapped_column(Uuid(as_uuid=False))
    runtime_control_instance_id: Mapped[Optional[str]] = mapped_column(
        Uuid(as_uuid=False)
    )
    runtime_control_token_hash: Mapped[Optional[str]] = mapped_column(String(64))

    canvas_container_id: Mapped[Optional[str]] = mapped_column(Text)
    canvas_desired_state: Mapped[str] = mapped_column(
        String(16), default="stopped", nullable=False
    )
    canvas_desired_revision: Mapped[int] = mapped_column(
        BigInteger, default=1, nullable=False
    )
    canvas_observed_revision: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )
    canvas_reason: Mapped[Optional[str]] = mapped_column(String(64))
    canvas_error_code: Mapped[Optional[str]] = mapped_column(String(64))
    canvas_last_transition_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    canvas_status: Mapped[str] = mapped_column(Text, default="stopped")
    canvas_created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    canvas_last_seen: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    canvas_internal_url: Mapped[Optional[str]] = mapped_column(Text)
    canvas_internal_port: Mapped[int] = mapped_column(Integer, default=3003)
    canvas_api_internal_port: Mapped[int] = mapped_column(Integer, default=3013)
    canvas_type: Mapped[str] = mapped_column(Text, default="default")
    canvas_manifest_status: Mapped[str] = mapped_column(Text, default="missing")
    canvas_last_sync_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    canvas_last_reset_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    terminal_internal_url: Mapped[Optional[str]] = mapped_column(String(512))

    workspace_firewall_egress_mode: Mapped[str] = mapped_column(
        Text,
        default="unrestricted",
        server_default=text("'unrestricted'"),
        nullable=False,
    )
    workspace_firewall_allowed_domains: Mapped[list[str]] = mapped_column(
        JSON, default=list, server_default=text("'[]'"), nullable=False
    )
    browser_firewall_egress_mode: Mapped[str] = mapped_column(
        Text,
        default="unrestricted",
        server_default=text("'unrestricted'"),
        nullable=False,
    )
    browser_firewall_allowed_domains: Mapped[list[str]] = mapped_column(
        JSON, default=list, server_default=text("'[]'"), nullable=False
    )
    firewall_revision: Mapped[int] = mapped_column(
        BigInteger, default=1, nullable=False
    )
    firewall_observed_revision: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )
    firewall_sync_status: Mapped[str] = mapped_column(
        String(32), default="pending", nullable=False
    )
    firewall_error_code: Mapped[Optional[str]] = mapped_column(String(64))
    firewall_target_delivery_id: Mapped[Optional[str]] = mapped_column(String(64))

    preferred_cli: Mapped[str] = mapped_column(Text, default="claude-code")
    agentic_tools: Mapped[list[str]] = mapped_column(JSON, default=list)
    agentic_capabilities: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    fallback_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    workspace_path: Mapped[str] = mapped_column(Text, default="/workspace")
    worktree_subdir: Mapped[str] = mapped_column(
        Text, default=".worktrees", nullable=False
    )
    acp_cli_args: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Browser container fields
    browser_container_id: Mapped[Optional[str]] = mapped_column(Text)
    browser_desired_state: Mapped[str] = mapped_column(
        String(16), default="stopped", nullable=False
    )
    browser_desired_revision: Mapped[int] = mapped_column(
        BigInteger, default=1, nullable=False
    )
    browser_observed_revision: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )
    browser_reason: Mapped[Optional[str]] = mapped_column(String(64))
    browser_error_code: Mapped[Optional[str]] = mapped_column(String(64))
    browser_last_transition_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    browser_credential_revision: Mapped[int] = mapped_column(
        BigInteger, default=1, nullable=False
    )
    browser_credential_observed_revision: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )
    browser_credential_key_id: Mapped[str] = mapped_column(
        Text, default="", nullable=False
    )
    browser_credential_observed_key_id: Mapped[Optional[str]] = mapped_column(Text)
    browser_credential_algorithm: Mapped[str] = mapped_column(
        String(32), default="hkdf-sha256-v1", nullable=False
    )
    browser_credential_observed_algorithm: Mapped[Optional[str]] = mapped_column(
        String(32)
    )
    browser_status: Mapped[str] = mapped_column(Text, default="stopped")
    browser_connectivity_state: Mapped[str] = mapped_column(
        String(32), default="pending", nullable=False
    )
    browser_connectivity_contract_version: Mapped[str] = mapped_column(
        Text, default="browser-connectivity/v1", nullable=False
    )
    browser_connectivity_admission: Mapped[str] = mapped_column(
        String(16), default="denied", nullable=False
    )
    browser_connectivity_browser_generation: Mapped[Optional[str]] = mapped_column(Text)
    browser_connectivity_profile_revision: Mapped[Optional[str]] = mapped_column(Text)
    browser_connectivity_credential_revision: Mapped[Optional[str]] = mapped_column(
        Text
    )
    browser_connectivity_accepted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    browser_connectivity_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    browser_connectivity_reason: Mapped[str] = mapped_column(
        String(64), default="BrowserConnectivityPending", nullable=False
    )
    browser_connectivity_error_code: Mapped[Optional[str]] = mapped_column(String(64))
    browser_connectivity_last_transition_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    browser_connectivity_backend_state: Mapped[str] = mapped_column(
        String(32), default="pending", nullable=False
    )
    browser_connectivity_backend_accepted_at: Mapped[Optional[datetime]] = (
        mapped_column(DateTime(timezone=True))
    )
    browser_connectivity_backend_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    browser_connectivity_backend_reason: Mapped[Optional[str]] = mapped_column(
        String(64)
    )
    browser_connectivity_backend_error_code: Mapped[Optional[str]] = mapped_column(
        String(64)
    )
    browser_connectivity_frontend_state: Mapped[str] = mapped_column(
        String(32), default="pending", nullable=False
    )
    browser_connectivity_frontend_accepted_at: Mapped[Optional[datetime]] = (
        mapped_column(DateTime(timezone=True))
    )
    browser_connectivity_frontend_expires_at: Mapped[Optional[datetime]] = (
        mapped_column(DateTime(timezone=True))
    )
    browser_connectivity_frontend_reason: Mapped[Optional[str]] = mapped_column(
        String(64)
    )
    browser_connectivity_frontend_error_code: Mapped[Optional[str]] = mapped_column(
        String(64)
    )
    browser_created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    browser_last_seen: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    # Browser WebRTC (neko) fields
    browser_webrtc_internal_url: Mapped[Optional[str]] = mapped_column(Text)
    browser_webrtc_internal_port: Mapped[int] = mapped_column(Integer, default=6080)

    # Browser CDP fields
    browser_cdp_internal_port: Mapped[int] = mapped_column(Integer, default=9223)

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
    firewall_sync_commands: Mapped[list["WorkspaceFirewallSyncCommand"]] = relationship(
        "WorkspaceFirewallSyncCommand",
        back_populates="workspace",
        cascade="all, delete-orphan",
        order_by="asc(WorkspaceFirewallSyncCommand.firewall_revision)",
    )
    shares: Mapped[list["WorkspaceShare"]] = relationship(
        "WorkspaceShare",
        back_populates="workspace",
        cascade="all, delete-orphan",
        order_by="asc(WorkspaceShare.created_at)",
    )
    knowledge_base_attachments: Mapped[list["WorkspaceKnowledgeBaseAttachment"]] = (
        relationship(
            "WorkspaceKnowledgeBaseAttachment",
            back_populates="workspace",
            cascade="all, delete-orphan",
            order_by="asc(WorkspaceKnowledgeBaseAttachment.created_at)",
        )
    )

    __table_args__ = (
        CheckConstraint(
            "bootstrap_revision >= 1 AND bootstrap_observed_revision >= 0 "
            "AND bootstrap_observed_revision <= bootstrap_revision",
            name="workspaces_bootstrap_revision_check",
        ),
        CheckConstraint(
            "bootstrap_status IN ('pending', 'running', 'succeeded', 'error')",
            name="workspaces_bootstrap_status_check",
        ),
        CheckConstraint(
            "runtime_desired_state IN ('running', 'stopped') "
            "AND browser_desired_state IN ('running', 'stopped') "
            "AND canvas_desired_state IN ('running', 'stopped')",
            name="workspaces_component_desired_state_check",
        ),
        CheckConstraint(
            "runtime_desired_revision >= 1 AND runtime_observed_revision >= 0 "
            "AND runtime_observed_revision <= runtime_desired_revision",
            name="workspaces_runtime_revision_check",
        ),
        CheckConstraint(
            "browser_desired_revision >= 1 AND browser_observed_revision >= 0 "
            "AND browser_observed_revision <= browser_desired_revision",
            name="workspaces_browser_revision_check",
        ),
        CheckConstraint(
            "canvas_desired_revision >= 1 AND canvas_observed_revision >= 0 "
            "AND canvas_observed_revision <= canvas_desired_revision",
            name="workspaces_canvas_revision_check",
        ),
        CheckConstraint(
            "browser_credential_revision >= 1 "
            "AND browser_credential_observed_revision >= 0 "
            "AND browser_credential_observed_revision <= browser_credential_revision",
            name="workspaces_browser_credential_revision_check",
        ),
        CheckConstraint(
            "browser_credential_algorithm = 'hkdf-sha256-v1' "
            "AND (browser_credential_observed_algorithm IS NULL "
            "OR browser_credential_observed_algorithm = 'hkdf-sha256-v1')",
            name="workspaces_browser_credential_algorithm_check",
        ),
        CheckConstraint(
            "runtime_status IN ('starting', 'running', 'stopping', 'stopped', "
            "'restarting', 'error', 'deleting')",
            name="workspaces_runtime_status_check",
        ),
        CheckConstraint(
            "knowledge_base_mount_active_revision >= 0 "
            "AND knowledge_base_mount_desired_revision >= "
            "knowledge_base_mount_active_revision "
            "AND knowledge_base_mount_observed_revision >= 0 "
            "AND knowledge_base_mount_observed_revision <= "
            "knowledge_base_mount_desired_revision",
            name="workspaces_knowledge_base_mount_revision_check",
        ),
        CheckConstraint(
            "knowledge_base_mount_sync_status IN "
            "('ready', 'preflighting', 'applying', 'compensating', 'degraded')",
            name="workspaces_knowledge_base_mount_sync_status_check",
        ),
        CheckConstraint(
            "provisioner IN ('docker', 'kubernetes')",
            name="workspaces_provisioner_check",
        ),
        CheckConstraint(
            "(runtime_control_instance_id IS NULL) = "
            "(runtime_control_token_hash IS NULL)",
            name="workspaces_runtime_control_pair_check",
        ),
        CheckConstraint(
            "(runtime_instance_id IS NULL AND "
            "runtime_control_instance_id IS NULL) OR "
            "runtime_instance_id = runtime_control_instance_id",
            name="workspaces_runtime_control_generation_check",
        ),
        CheckConstraint(
            "runtime_control_token_hash IS NULL OR "
            "(length(runtime_control_token_hash) = 64 AND "
            "runtime_control_token_hash = lower(runtime_control_token_hash))",
            name="workspaces_runtime_control_token_hash_check",
        ),
        CheckConstraint(
            "workspace_firewall_egress_mode IN "
            "('blocked', 'allowlist', 'unrestricted')",
            name="workspaces_workspace_firewall_egress_mode_check",
        ),
        CheckConstraint(
            "browser_firewall_egress_mode IN "
            "('blocked', 'allowlist', 'unrestricted')",
            name="workspaces_browser_firewall_egress_mode_check",
        ),
        CheckConstraint(
            "(workspace_firewall_egress_mode = 'allowlist' "
            "AND json_array_length(workspace_firewall_allowed_domains) > 0) "
            "OR (workspace_firewall_egress_mode != 'allowlist' "
            "AND json_array_length(workspace_firewall_allowed_domains) = 0)",
            name="workspace_firewall_allowed_domains_match_egress_mode",
        ),
        CheckConstraint(
            "(browser_firewall_egress_mode = 'allowlist' "
            "AND json_array_length(browser_firewall_allowed_domains) > 0) "
            "OR (browser_firewall_egress_mode != 'allowlist' "
            "AND json_array_length(browser_firewall_allowed_domains) = 0)",
            name="browser_firewall_allowed_domains_match_egress_mode",
        ),
        CheckConstraint(
            "firewall_revision >= 1",
            name="workspaces_firewall_revision_check",
        ),
        CheckConstraint(
            "firewall_observed_revision >= 0 AND "
            "firewall_observed_revision <= firewall_revision",
            name="workspaces_firewall_observed_revision_check",
        ),
        CheckConstraint(
            "firewall_sync_status IN "
            "('pending', 'applying', 'applied', 'error', 'unavailable')",
            name="workspaces_firewall_sync_status_check",
        ),
        CheckConstraint(
            "browser_status IN ('stopped', 'starting', 'running', 'error', 'restarting')",
            name="workspaces_browser_status_check",
        ),
        CheckConstraint(
            "browser_connectivity_state IN "
            "('pending', 'ready', 'degraded', 'not_ready', 'unavailable')",
            name="workspaces_browser_connectivity_state_check",
        ),
        CheckConstraint(
            "browser_connectivity_admission IN ('allowed', 'denied')",
            name="workspaces_browser_connectivity_admission_check",
        ),
        CheckConstraint(
            "browser_connectivity_backend_state IN "
            "('pending', 'ready', 'degraded', 'not_ready', 'unavailable')",
            name="workspaces_browser_connectivity_backend_state_check",
        ),
        CheckConstraint(
            "browser_connectivity_frontend_state IN "
            "('pending', 'ready', 'degraded', 'not_ready', 'unavailable')",
            name="workspaces_browser_connectivity_frontend_state_check",
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


class UserGroup(Base):
    """Product user group."""

    __tablename__ = "user_groups"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    members: Mapped[list["UserGroupMember"]] = relationship(
        "UserGroupMember",
        back_populates="group",
        cascade="all, delete-orphan",
        order_by="asc(UserGroupMember.created_at)",
    )


class UserGroupMember(Base):
    """User group membership."""

    __tablename__ = "user_group_members"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    group_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("user_groups.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_by_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    group: Mapped[UserGroup] = relationship("UserGroup", back_populates="members")
    user: Mapped[User] = relationship("User")

    __table_args__ = (
        UniqueConstraint(
            "group_id", "user_id", name="user_group_members_group_user_unique"
        ),
    )


class AuditEvent(Base):
    """Structured audit event."""

    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    actor_user_id: Mapped[Optional[str]] = mapped_column(
        String(128),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_type: Mapped[str] = mapped_column(String(128), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    error_code: Mapped[Optional[str]] = mapped_column(String(64))
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    root_correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('user', 'service')",
            name="audit_events_actor_type_check",
        ),
        CheckConstraint(
            "actor_type = 'user' OR actor_user_id IS NULL",
            name="audit_events_service_actor_user_check",
        ),
        CheckConstraint(
            "result IN ('success', 'failure', 'compensation_required')",
            name="audit_events_result_check",
        ),
        CheckConstraint(
            "(result = 'success' AND error_code IS NULL) OR "
            "(result IN ('failure', 'compensation_required') "
            "AND error_code IS NOT NULL AND length(error_code) > 0)",
            name="audit_events_result_error_check",
        ),
        Index(
            "ix_audit_events_correlation_created",
            "correlation_id",
            "created_at",
        ),
        Index(
            "ix_audit_events_root_correlation_created",
            "root_correlation_id",
            "created_at",
        ),
        Index(
            "ix_audit_events_target_created",
            "target_type",
            "target_id",
            "created_at",
        ),
    )


class WorkspaceShare(Base):
    """Workspace share authorization"""

    __tablename__ = "workspace_shares"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
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
    granted_by_user: Mapped[User] = relationship(
        "User",
        back_populates="workspace_shares_granted",
        foreign_keys=[granted_by_user_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "target_type",
            "target_id",
            name="workspace_shares_workspace_target_unique",
        ),
        CheckConstraint(
            "target_type IN ('user', 'user_group')",
            name="workspace_shares_target_type_check",
        ),
        CheckConstraint(
            "role IN ('reader', 'manager')",
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
    owner_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    current_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quota_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    version_control_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    last_indexed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_index_status: Mapped[Optional[str]] = mapped_column(String(32))
    last_index_error: Mapped[Optional[str]] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(
        String(16),
        default="private",
        server_default=text("'private'"),
        nullable=False,
    )
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
        CheckConstraint(
            "visibility IN ('private', 'public')",
            name="knowledge_bases_visibility_check",
        ),
    )


class PlatformResourceActivityEvent(Base):
    """Privacy-minimized semantic activity ledger."""

    __tablename__ = "platform_resource_activity_events"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "resource_type IN ('workspace', 'knowledge_base')",
            name="platform_resource_activity_type_check",
        ),
        CheckConstraint(
            "source IN ('manager', 'runtime')",
            name="platform_resource_activity_source_check",
        ),
        Index(
            "ix_platform_resource_activity_type_occurred",
            "resource_type",
            "occurred_at",
        ),
        Index(
            "ix_platform_resource_activity_resource_occurred",
            "resource_type",
            "resource_id",
            "occurred_at",
        ),
    )


class PlatformResourceTelemetryBatch(Base):
    """Idempotency ledger for Runtime telemetry deliveries."""

    __tablename__ = "platform_resource_telemetry_batches"

    batch_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    runtime_instance_id: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        Index(
            "ix_platform_resource_telemetry_batch_workspace_received",
            "workspace_id",
            "received_at",
        ),
    )


class PlatformResourceDailyActiveResource(Base):
    """Distinct active resource membership for one platform-local day."""

    __tablename__ = "platform_resource_daily_active_resources"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    local_date: Mapped[str] = mapped_column(String(10), nullable=False)
    time_zone: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False)
    first_occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "local_date",
            "time_zone",
            "resource_type",
            "resource_id",
            name="platform_resource_daily_active_unique",
        ),
        Index(
            "ix_platform_resource_daily_active_lookup",
            "resource_type",
            "local_date",
        ),
    )


class PlatformResourceDailyMetric(Base):
    """Permanent resource-count aggregate for one platform-local day."""

    __tablename__ = "platform_resource_daily_metrics"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    local_date: Mapped[str] = mapped_column(String(10), nullable=False)
    time_zone: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    end_of_day_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deleted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    collection_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "local_date",
            "time_zone",
            "resource_type",
            name="platform_resource_daily_metric_unique",
        ),
    )


class ResourceCapacityObservation(Base):
    """Latest successful capacity observation for one resource storage kind."""

    __tablename__ = "resource_capacity_observations"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    used_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    allocated_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    host_available_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    provisioner: Mapped[str] = mapped_column(String(32), nullable=False)
    measured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    measurement_source: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "resource_type",
            "resource_id",
            "storage_kind",
            name="resource_capacity_observation_unique",
        ),
        CheckConstraint(
            "storage_kind IN ('workspace_data', 'runtime_home', 'knowledge_base')",
            name="resource_capacity_observation_storage_kind_check",
        ),
        Index(
            "ix_resource_capacity_observation_resource",
            "resource_type",
            "resource_id",
        ),
    )


class ResourceCapacityDailySnapshot(Base):
    """Permanent per-resource daily capacity snapshot."""

    __tablename__ = "resource_capacity_daily_snapshots"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    local_date: Mapped[str] = mapped_column(String(10), nullable=False)
    time_zone: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    used_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    allocated_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    host_available_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    measured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "local_date",
            "time_zone",
            "resource_type",
            "resource_id",
            "storage_kind",
            name="resource_capacity_daily_snapshot_unique",
        ),
    )


class PlatformResourceCapacityDailyMetric(Base):
    """Permanent platform-level daily capacity aggregate."""

    __tablename__ = "platform_resource_capacity_daily_metrics"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    local_date: Mapped[str] = mapped_column(String(10), nullable=False)
    time_zone: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    used_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    allocated_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    unknown_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stale_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "local_date",
            "time_zone",
            "resource_type",
            "storage_kind",
            name="platform_resource_capacity_daily_metric_unique",
        ),
    )


class WorkspaceStorageAllocation(Base):
    """Manager-owned desired and observed Workspace storage state."""

    __tablename__ = "workspace_storage_allocations"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    workspace_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    storage_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    desired_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    observed_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    observed_revision: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    expansion_supported: Mapped[Optional[bool]] = mapped_column(Boolean)
    phase: Mapped[str] = mapped_column(String(16), nullable=False, default="completed")
    operator_error_code: Mapped[Optional[str]] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "storage_kind",
            name="workspace_storage_allocation_unique",
        ),
    )


class WorkspaceCapacityExpansionRequest(Base):
    """Auditable asynchronous Workspace PVC expansion request."""

    __tablename__ = "workspace_capacity_expansion_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    storage_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    requested_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    target_revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    requested_by_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    phase: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    error_code: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "phase IN ('pending', 'applying', 'completed', 'failed')",
            name="workspace_capacity_expansion_phase_check",
        ),
        Index(
            "ux_workspace_capacity_expansion_active",
            "workspace_id",
            "storage_kind",
            unique=True,
            postgresql_where=text("phase IN ('pending', 'applying')"),
            sqlite_where=text("phase IN ('pending', 'applying')"),
        ),
    )


class KnowledgeBaseShare(Base):
    """Knowledge base share authorization"""

    __tablename__ = "knowledge_base_shares"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kb_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
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
    granted_by: Mapped[User] = relationship(
        "User",
        back_populates="knowledge_base_shares_granted",
        foreign_keys=[granted_by_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "kb_id",
            "target_type",
            "target_id",
            name="knowledge_base_shares_kb_target_unique",
        ),
        CheckConstraint(
            "target_type IN ('user', 'user_group')",
            name="knowledge_base_shares_target_type_check",
        ),
        CheckConstraint(
            "role IN ('reader', 'manager')",
            name="knowledge_base_shares_role_check",
        ),
    )


class WorkspaceKnowledgeBaseAttachment(Base):
    """Last-known-good Workspace and knowledge base attachment."""

    __tablename__ = "workspace_knowledge_base_attachments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    kb_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("knowledge_bases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    mount_alias: Mapped[str] = mapped_column(String(255), nullable=False)
    attached_by_id: Mapped[Optional[str]] = mapped_column(
        String(128), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
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
    attached_by: Mapped[Optional[User]] = relationship(
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

    workspace: Mapped[Workspace] = relationship(
        "Workspace", back_populates="runtime_logs"
    )


class WorkspaceFirewallSyncCommand(Base):
    """Durable desired firewall delivery command."""

    __tablename__ = "workspace_firewall_sync_commands"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    firewall_revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    retry_of_command_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("workspace_firewall_sync_commands.id", ondelete="SET NULL"),
    )
    root_command_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("workspace_firewall_sync_commands.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    lease_owner: Mapped[Optional[str]] = mapped_column(String(128))
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    last_error_code: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    workspace: Mapped[Workspace] = relationship(
        "Workspace", back_populates="firewall_sync_commands"
    )

    __table_args__ = (
        CheckConstraint(
            "firewall_revision >= 1",
            name="workspace_firewall_sync_commands_revision_check",
        ),
        CheckConstraint(
            "attempt_count >= 0",
            name="workspace_firewall_sync_commands_attempt_count_check",
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'delivered', 'superseded', 'failed')",
            name="workspace_firewall_sync_commands_status_check",
        ),
        CheckConstraint(
            "(status = 'processing' AND lease_owner IS NOT NULL "
            "AND lease_expires_at IS NOT NULL) OR "
            "(status <> 'processing' AND lease_owner IS NULL "
            "AND lease_expires_at IS NULL)",
            name="workspace_firewall_sync_commands_lease_check",
        ),
        Index(
            "ix_workspace_firewall_sync_commands_claim",
            "status",
            "next_attempt_at",
            "lease_expires_at",
        ),
        Index(
            "ix_workspace_firewall_sync_commands_lineage",
            "workspace_id",
            "firewall_revision",
            "root_command_id",
            "created_at",
        ),
    )


class WorkspaceRuntimeJob(Base):
    """Workspace runtime background task schedule"""

    __tablename__ = "workspace_runtime_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    operation: Mapped[str] = mapped_column(String(32), nullable=False)
    target_component: Mapped[Optional[str]] = mapped_column(String(16))
    strategy: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    target_revision: Mapped[Optional[int]] = mapped_column(BigInteger)
    target_runtime_instance_id: Mapped[Optional[str]] = mapped_column(
        Uuid(as_uuid=False)
    )
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    root_correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    job_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    lifecycle_job_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("workspace_runtime_jobs.id", ondelete="SET NULL"),
    )
    retry_of_job_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("workspace_runtime_jobs.id", ondelete="SET NULL"),
    )
    claim_token: Mapped[Optional[str]] = mapped_column(String(64))
    claim_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    last_heartbeat_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    dispatch_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[Optional[str]] = mapped_column(String(64))

    workspace: Mapped[Workspace] = relationship(
        "Workspace", back_populates="runtime_jobs"
    )

    __table_args__ = (
        CheckConstraint(
            "operation IN ('knowledge_base_mount_reconcile', 'workspace_access_recycle', "
            "'workspace_start', 'workspace_stop', 'workspace_delete', "
            "'runtime_restart', 'browser_restart', 'canvas_restart', "
            "'browser_credential_rotate')",
            name="workspace_runtime_jobs_operation_check",
        ),
        CheckConstraint(
            "target_component IS NULL OR "
            "target_component IN ('runtime', 'browser', 'canvas')",
            name="workspace_runtime_jobs_target_component_check",
        ),
        CheckConstraint(
            "((operation = 'runtime_restart' AND target_component = 'runtime') OR "
            "(operation IN ('browser_restart', 'browser_credential_rotate') "
            "AND target_component = 'browser') OR "
            "(operation = 'canvas_restart' AND target_component = 'canvas') OR "
            "(operation NOT IN ('runtime_restart', 'browser_restart', "
            "'canvas_restart', 'browser_credential_rotate') "
            "AND target_component IS NULL))",
            name="workspace_runtime_jobs_operation_component_check",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'superseded')",
            name="workspace_runtime_jobs_status_check",
        ),
        CheckConstraint(
            "strategy IN ('docker', 'kubernetes')",
            name="workspace_runtime_jobs_strategy_check",
        ),
        CheckConstraint(
            "retries >= 0 AND dispatch_attempts >= 0",
            name="workspace_runtime_jobs_attempts_check",
        ),
        CheckConstraint(
            "((operation IN ('knowledge_base_mount_reconcile', "
            "'workspace_access_recycle') AND target_component IS NULL "
            "AND target_revision IS NOT NULL AND target_revision >= 0) OR "
            "(operation IN ('workspace_start', 'workspace_stop', "
            "'workspace_delete') AND target_component IS NULL "
            "AND target_revision IS NULL) OR "
            "(operation IN ('runtime_restart', 'browser_restart', "
            "'canvas_restart', 'browser_credential_rotate') "
            "AND target_component IS NOT NULL "
            "AND target_revision IS NOT NULL AND target_revision >= 1))",
            name="workspace_runtime_jobs_target_revision_check",
        ),
        CheckConstraint(
            "((status = 'queued' AND claim_token IS NULL "
            "AND claim_expires_at IS NULL AND last_heartbeat_at IS NULL "
            "AND started_at IS NULL AND finished_at IS NULL "
            "AND error_code IS NULL) OR "
            "(status = 'running' AND claim_token IS NOT NULL "
            "AND claim_expires_at IS NOT NULL AND last_heartbeat_at IS NOT NULL "
            "AND started_at IS NOT NULL AND finished_at IS NULL "
            "AND error_code IS NULL) OR "
            "(status IN ('succeeded', 'superseded') "
            "AND claim_token IS NULL AND claim_expires_at IS NULL "
            "AND finished_at IS NOT NULL AND error_code IS NULL) OR "
            "(status = 'failed' AND claim_token IS NULL "
            "AND claim_expires_at IS NULL AND finished_at IS NOT NULL "
            "AND error_code IS NOT NULL AND length(error_code) > 0))",
            name="workspace_runtime_jobs_state_fields_check",
        ),
        CheckConstraint(
            "lifecycle_job_id IS NULL OR lifecycle_job_id <> id",
            name="workspace_runtime_jobs_lifecycle_self_check",
        ),
        CheckConstraint(
            "retry_of_job_id IS NULL OR retry_of_job_id <> id",
            name="workspace_runtime_jobs_retry_self_check",
        ),
        Index(
            "uq_workspace_runtime_jobs_queued_workspace_operation",
            "workspace_id",
            unique=True,
            postgresql_where=text(
                "status = 'queued' AND "
                "operation IN ('workspace_start', 'workspace_stop', 'workspace_delete')"
            ),
            sqlite_where=text(
                "status = 'queued' AND "
                "operation IN ('workspace_start', 'workspace_stop', 'workspace_delete')"
            ),
        ),
        Index(
            "uq_workspace_runtime_jobs_running_workspace_operation",
            "workspace_id",
            unique=True,
            postgresql_where=text(
                "status = 'running' AND "
                "operation IN ('workspace_start', 'workspace_stop', 'workspace_delete')"
            ),
            sqlite_where=text(
                "status = 'running' AND "
                "operation IN ('workspace_start', 'workspace_stop', 'workspace_delete')"
            ),
        ),
        Index(
            "uq_workspace_runtime_jobs_queued_component_operation",
            "workspace_id",
            "target_component",
            unique=True,
            postgresql_where=text("status = 'queued' AND target_component IS NOT NULL"),
            sqlite_where=text("status = 'queued' AND target_component IS NOT NULL"),
        ),
        Index(
            "uq_workspace_runtime_jobs_running_component_operation",
            "workspace_id",
            "target_component",
            unique=True,
            postgresql_where=text(
                "status = 'running' AND target_component IS NOT NULL"
            ),
            sqlite_where=text("status = 'running' AND target_component IS NOT NULL"),
        ),
    )


class AutomationJob(Base):
    """Automation job definition."""

    __tablename__ = "automation_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    creator_user_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    trigger: Mapped[str] = mapped_column(String(32), nullable=False)
    schedule: Mapped[str] = mapped_column(String(255), nullable=False)
    exact: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    agentic_tool: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    agent_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    worktree_key: Mapped[str] = mapped_column(Text, nullable=False)
    worktree_branch: Mapped[str] = mapped_column(Text, nullable=False)
    notification_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    creator: Mapped[User] = relationship("User")
    workspace: Mapped[Workspace] = relationship("Workspace")
    executions: Mapped[list["AutomationExecution"]] = relationship(
        "AutomationExecution",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="desc(AutomationExecution.scheduled_for)",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'paused', 'completed')",
            name="automation_jobs_status_check",
        ),
        CheckConstraint(
            "trigger IN ('cron', 'manual', 'webhook', 'at', 'every')",
            name="automation_jobs_trigger_check",
        ),
    )


class AutomationExecution(Base):
    """Immutable automation execution snapshot and lifecycle."""

    __tablename__ = "automation_executions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("automation_jobs.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    trigger: Mapped[str] = mapped_column(String(32), nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    queued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    runner_instance_id: Mapped[Optional[str]] = mapped_column(String(128))
    claim_request_id: Mapped[Optional[str]] = mapped_column(String(128))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    cancel_requested_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    principal_user_id_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    agentic_tool_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    model_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    agent_config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    worktree_key_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    error_code: Mapped[Optional[str]] = mapped_column(String(128))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    notification_status: Mapped[Optional[str]] = mapped_column(String(16))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    job: Mapped[AutomationJob] = relationship(
        "AutomationJob", back_populates="executions"
    )
    workspace: Mapped[Workspace] = relationship("Workspace")

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'success', 'failed', 'cancelled')",
            name="automation_executions_status_check",
        ),
        CheckConstraint(
            "trigger IN ('cron', 'manual', 'webhook', 'at', 'every')",
            name="automation_executions_trigger_check",
        ),
        CheckConstraint(
            "notification_status IN ('delivered', 'failed')",
            name="automation_executions_notification_status_check",
        ),
        Index(
            "uq_automation_executions_running_job",
            "job_id",
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
        Index(
            "uq_automation_executions_claim_request",
            "workspace_id",
            "claim_request_id",
            unique=True,
            postgresql_where=text("claim_request_id IS NOT NULL"),
        ),
        Index(
            "ix_automation_executions_workspace_claim",
            "workspace_id",
            "status",
            "scheduled_for",
            "id",
        ),
        Index(
            "ix_automation_executions_job_fifo",
            "job_id",
            "status",
            "scheduled_for",
            "id",
        ),
    )


class MarketplaceActivity(Base):
    """Append-only Marketplace audit event."""

    __tablename__ = "marketplace_activities"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    operation_id: Mapped[Optional[str]] = mapped_column(String(64))
    workspace_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("workspaces.id", ondelete="SET NULL")
    )
    workspace_id_snapshot: Mapped[Optional[str]] = mapped_column(String(64))
    package_format: Mapped[Optional[str]] = mapped_column(String(32))
    target_client: Mapped[Optional[str]] = mapped_column(String(32))
    package_id: Mapped[Optional[str]] = mapped_column(String(255))
    catalog_plugin_id: Mapped[Optional[str]] = mapped_column(String(1024))
    release_revision: Mapped[Optional[str]] = mapped_column(String(64))
    profile_digest: Mapped[Optional[str]] = mapped_column(String(64))
    projection_digest: Mapped[Optional[str]] = mapped_column(String(64))
    materialization_digest: Mapped[Optional[str]] = mapped_column(String(64))
    projected_count: Mapped[Optional[int]] = mapped_column(Integer)
    skipped_count: Mapped[Optional[int]] = mapped_column(Integer)
    conflict_count: Mapped[Optional[int]] = mapped_column(Integer)
    created_count: Mapped[Optional[int]] = mapped_column(Integer)
    merged_count: Mapped[Optional[int]] = mapped_column(Integer)
    unchanged_count: Mapped[Optional[int]] = mapped_column(Integer)
    overwritten_count: Mapped[Optional[int]] = mapped_column(Integer)
    target_locators: Mapped[list[str]] = mapped_column(
        JSON, default=list, server_default=text("'[]'"), nullable=False
    )
    diagnostic_codes: Mapped[list[str]] = mapped_column(
        JSON, default=list, server_default=text("'[]'"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    marketplace_id: Mapped[Optional[str]] = mapped_column(String(64))
    source_id: Mapped[Optional[str]] = mapped_column(String(255))
    error_code: Mapped[Optional[str]] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "package_format IS NULL OR package_format IN "
            "('codex-native', 'claude-native', 'agent-plugin/1.0.0')",
            name="marketplace_activities_package_format_check",
        ),
        CheckConstraint(
            "target_client IS NULL OR target_client IN ('claude-code', 'codex')",
            name="marketplace_activities_target_client_check",
        ),
        CheckConstraint(
            "action IN ('install', 'copy', 'import', 'delete')",
            name="marketplace_activities_action_check",
        ),
        CheckConstraint(
            "status IN ('succeeded', 'failed')",
            name="marketplace_activities_status_check",
        ),
        Index(
            "ix_marketplace_activities_workspace_created",
            "workspace_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_marketplace_activities_actor_created",
            "actor_user_id",
            "created_at",
            "id",
        ),
    )


class MarketplaceCommandResult(Base):
    """Append-only child receipt for one target-client CLI invocation."""

    __tablename__ = "marketplace_command_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    activity_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("marketplace_activities.id", ondelete="CASCADE"),
        nullable=False,
    )
    operation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    argv_display: Mapped[str] = mapped_column(String(4096), nullable=False)
    exit_code: Mapped[Optional[int]] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stdout: Mapped[Optional[str]] = mapped_column(Text)
    stderr: Mapped[Optional[str]] = mapped_column(Text)
    stdout_original_byte_count: Mapped[int] = mapped_column(Integer, nullable=False)
    stderr_original_byte_count: Mapped[int] = mapped_column(Integer, nullable=False)
    truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint(
            "activity_id", "sequence", name="uq_marketplace_command_results_sequence"
        ),
        Index("ix_marketplace_command_results_operation", "operation_id", "sequence"),
    )
