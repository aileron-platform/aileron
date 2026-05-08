"""Database seed data loader

Note: User data has been created by init SQL, this file is only responsible for dynamic data such as model configuration
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.database import SessionLocal
from app.db.models import (
    ModelConfig,
    Workspace,
    User,
)

logger = logging.getLogger(__name__)

DOCKER_DEFAULT_BROWSER_WEBRTC_EXTERNAL_PORT = 52330
DOCKER_DEFAULT_BROWSER_WEBRTC_EXTERNAL_URL = (
    f"http://localhost:{DOCKER_DEFAULT_BROWSER_WEBRTC_EXTERNAL_PORT}"
)


def should_create_default_workspace() -> bool:
    """Determine if default workspace needs to be created based on deployment mode."""
    settings = get_settings()
    if settings.RUNTIME_PROVISIONER == "kubernetes":
        return settings.BOOTSTRAP_DEFAULT_WORKSPACE_ENABLED
    return True


def _get_default_workspace_owner(db: Session) -> Optional[User]:
    settings = get_settings()
    return (
        db.query(User)
        .filter(User.email == settings.BOOTSTRAP_DEFAULT_WORKSPACE_OWNER_EMAIL)
        .first()
    )


def _create_docker_default_workspace(default_user: User) -> Workspace:
    return Workspace(
        id="default-workspace",
        owner_id=default_user.id,
        name="Default Workspace",
        description="Aileron default development workspace",
        branch="main",
        runtime="universal",
        provisioner="docker",
        target_namespace=None,
        env_vars=[],
        runtime_status="running",
        runtime_internal_url="http://workspace-runtime-default-workspace:3002",
        runtime_external_url="http://localhost:3002",
        runtime_internal_port=3002,
        runtime_external_port=3002,
        terminal_external_port=3004,
        terminal_external_url="http://localhost:3004",
        browser_container_id="workspace-browser-default-workspace",
        browser_status="running",
        browser_webrtc_internal_url="http://workspace-browser-default-workspace:6080",
        browser_webrtc_external_url=DOCKER_DEFAULT_BROWSER_WEBRTC_EXTERNAL_URL,
        browser_webrtc_internal_port=6080,
        browser_webrtc_external_port=DOCKER_DEFAULT_BROWSER_WEBRTC_EXTERNAL_PORT,
        browser_cdp_internal_port=9223,
        browser_cdp_external_port=9223,
        canvas_container_id="workspace-canvas-default-workspace",
        canvas_status="running",
        canvas_internal_url="http://workspace-canvas-default-workspace:3003",
        canvas_external_url="http://localhost:3003",
        canvas_internal_port=3003,
        canvas_external_port=3003,
        canvas_api_internal_port=3013,
        canvas_type="default",
        canvas_manifest_status="missing",
        workspace_firewall_network_access_enabled=True,
        workspace_firewall_domain_access_mode="all",
        workspace_firewall_allowed_domains=[],
        browser_firewall_network_access_enabled=True,
        browser_firewall_domain_access_mode="all",
        browser_firewall_allowed_domains=[],
        cli_type="claude-code",
        workspace_path="/workspace",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def _reconcile_existing_docker_default_workspace(workspace: Workspace) -> bool:
    if workspace.provisioner != "docker":
        return False

    changed = False

    if (
        workspace.browser_webrtc_external_port
        != DOCKER_DEFAULT_BROWSER_WEBRTC_EXTERNAL_PORT
    ):
        workspace.browser_webrtc_external_port = (
            DOCKER_DEFAULT_BROWSER_WEBRTC_EXTERNAL_PORT
        )
        changed = True

    if (
        workspace.browser_webrtc_external_url
        != DOCKER_DEFAULT_BROWSER_WEBRTC_EXTERNAL_URL
    ):
        workspace.browser_webrtc_external_url = (
            DOCKER_DEFAULT_BROWSER_WEBRTC_EXTERNAL_URL
        )
        changed = True

    if changed:
        workspace.updated_at = datetime.utcnow()

    return changed


def _create_kubernetes_default_workspace(default_user: User) -> Workspace:
    settings = get_settings()
    target_namespace = (
        settings.BOOTSTRAP_DEFAULT_WORKSPACE_TARGET_NAMESPACE
        or settings.RUNTIME_K8S_NAMESPACE
    )
    git_url = settings.BOOTSTRAP_DEFAULT_WORKSPACE_GIT_URL or None
    workspace_id = settings.BOOTSTRAP_DEFAULT_WORKSPACE_ID

    return Workspace(
        id=workspace_id,
        owner_id=default_user.id,
        name="Default Workspace",
        description="Aileron default development workspace",
        git_url=git_url,
        branch=settings.BOOTSTRAP_DEFAULT_WORKSPACE_BRANCH,
        runtime="universal",
        provisioner="kubernetes",
        target_namespace=target_namespace,
        env_vars=[],
        runtime_status="starting",
        runtime_internal_port=3002,
        browser_status="starting",
        browser_webrtc_internal_port=6080,
        browser_cdp_internal_port=9223,
        canvas_status="starting",
        canvas_internal_port=3003,
        canvas_api_internal_port=3013,
        canvas_type="default",
        canvas_manifest_status="missing",
        workspace_firewall_network_access_enabled=True,
        workspace_firewall_domain_access_mode="all",
        workspace_firewall_allowed_domains=[],
        browser_firewall_network_access_enabled=True,
        browser_firewall_domain_access_mode="all",
        browser_firewall_allowed_domains=[],
        cli_type="claude-code",
        workspace_path="/workspace",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def create_default_model_configs(db: Session) -> None:
    """Create default model configuration"""
    # Check if model configuration already exists
    existing_configs = db.query(ModelConfig).count()
    if existing_configs > 0:
        logger.info("Model configuration already exists, skipping creating default configuration")
        return

    # Claude model configuration
    model_configs = [
        ModelConfig(
            id="model-sonnet-4",
            model_key="claude-sonnet-4",
            model_name="Claude 3.5 Sonnet (New)",
            anthropic_model_id="claude-3-5-sonnet-20241022",
            is_active=True,
            sort_order=1
        ),
        ModelConfig(
            id="model-sonnet-legacy",
            model_key="claude-3-5-sonnet-20240620",
            model_name="Claude 3.5 Sonnet (Legacy)",
            anthropic_model_id="claude-3-5-sonnet-20240620",
            is_active=True,
            sort_order=2
        ),
        ModelConfig(
            id="model-haiku",
            model_key="claude-3-haiku-20240307",
            model_name="Claude 3 Haiku",
            anthropic_model_id="claude-3-haiku-20240307",
            is_active=True,
            sort_order=3
        ),
        ModelConfig(
            id="model-opus",
            model_key="claude-3-opus-20240229",
            model_name="Claude 3 Opus",
            anthropic_model_id="claude-3-opus-20240229",
            is_active=True,
            sort_order=4
        )
    ]

    db.add_all(model_configs)
    logger.info("Created 4 default model configurations")


def create_default_workspace(db: Session) -> None:
    """Create default workspace (default-workspace)"""
    settings = get_settings()

    if not should_create_default_workspace():
        logger.info("Current settings do not enable default workspace bootstrap, skipping creation")
        return

    # Check if default-workspace already exists
    workspace_id = settings.BOOTSTRAP_DEFAULT_WORKSPACE_ID
    existing_workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if existing_workspace:
        if _reconcile_existing_docker_default_workspace(existing_workspace):
            logger.info(
                "Updated existing docker default workspace browser WebRTC contract: %s",
                existing_workspace.id,
            )
        else:
            logger.info("Default workspace already exists, skipping creation")
        return

    # GetDefaultUser
    default_user = _get_default_workspace_owner(db)
    if not default_user:
        logger.warning("Default user not found, unable to create default workspace")
        return

    if settings.RUNTIME_PROVISIONER == "kubernetes":
        default_workspace = _create_kubernetes_default_workspace(default_user)
    else:
        default_workspace = _create_docker_default_workspace(default_user)

    db.add(default_workspace)
    logger.info("CreateDefault workspace: %s", default_workspace.id)


def ensure_bootstrap_default_workspace(
    *,
    max_attempts: int = 5,
    retry_interval_seconds: float = 2.0,
) -> bool:
    """Ensure bootstrap default workspace exists.

    # On first Kubernetes installation, workspace-manager may start before init SQL creates the admin user.
    # Use a brief retry here to avoid permanently skipping default workspace on first start.
    """
    settings = get_settings()
    workspace_id = settings.BOOTSTRAP_DEFAULT_WORKSPACE_ID

    for attempt in range(1, max_attempts + 1):
        db: Session = SessionLocal()
        try:
            existing_workspace = (
                db.query(Workspace).filter(Workspace.id == workspace_id).first()
            )
            if existing_workspace:
                logger.info("Bootstrap default workspace already exists: %s", workspace_id)
                return True

            create_default_workspace(db)
            db.commit()

            existing_workspace = (
                db.query(Workspace).filter(Workspace.id == workspace_id).first()
            )
            if existing_workspace:
                logger.info(
                    "Bootstrap default workspace creation completed: %s (attempt %s/%s)",
                    workspace_id,
                    attempt,
                    max_attempts,
                )
                return True

            logger.info(
                "Bootstrap default workspace creation not yet complete, retrying later (attempt %s/%s)",
                attempt,
                max_attempts,
            )
        except Exception:
            db.rollback()
            logger.exception(
                "bootstrap Default workspace CreateFailed (attempt %s/%s)",
                attempt,
                max_attempts,
            )
        finally:
            db.close()

        if attempt < max_attempts:
            time.sleep(retry_interval_seconds)

    logger.warning("Bootstrap default workspace creation retry completed but still does not exist: %s", workspace_id)
    return False


def load_seed_data() -> None:
    """Load seed data (users created by init SQL, default workspace only for Docker mode)"""
    logger.info("Starting to load seed data...")

    db: Session = SessionLocal()
    try:
        # Create default model configurations
        create_default_model_configs(db)

        # Create default workspace
        create_default_workspace(db)

        # Commit changes
        db.commit()
        logger.info("✅ Seed data loading completed")

    except Exception as e:
        logger.error(f"❌ Seed data loading failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    load_seed_data()
