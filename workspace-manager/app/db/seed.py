"""資料庫種子資料載入器

注意：使用者資料已由 init SQL 建立，此檔案僅負責模型配置等動態資料
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
    TemplateCategory,
    TemplateFeature,
    TemplateFeatureCliType,
)

logger = logging.getLogger(__name__)

DOCKER_DEFAULT_BROWSER_WEBRTC_EXTERNAL_PORT = 52330
DOCKER_DEFAULT_BROWSER_WEBRTC_EXTERNAL_URL = (
    f"http://localhost:{DOCKER_DEFAULT_BROWSER_WEBRTC_EXTERNAL_PORT}"
)

DEFAULT_TEMPLATE_CATEGORIES = [
    {
        "id": "general",
        "name": "General",
        "description": "Templates that do not belong to a specific category yet",
        "icon": "folder",
        "sort_order": 1,
    },
    {
        "id": "automation",
        "name": "Automation",
        "description": "Templates for workflows, automation tasks, and scheduling",
        "icon": "workflow",
        "sort_order": 2,
    },
    {
        "id": "documentation",
        "name": "Documentation",
        "description": "Templates for docs, knowledge bases, and content writing",
        "icon": "file-text",
        "sort_order": 3,
    },
    {
        "id": "web",
        "name": "Web Development",
        "description": "Templates for websites and web application development",
        "icon": "globe",
        "sort_order": 4,
    },
    {
        "id": "devops",
        "name": "DevOps",
        "description": "Templates for deployment, CI/CD, and infrastructure",
        "icon": "wrench",
        "sort_order": 5,
    },
]

DEFAULT_TEMPLATE_FEATURES = [
    {
        "id": "feature-mcp",
        "feature_key": "mcp",
        "feature_name": "MCP Servers",
        "description": "Model Context Protocol server support",
        "icon": "server",
        "sort_order": 1,
        "cli_types": ["claude-code", "codex", "gemini"],
    },
    {
        "id": "feature-commands",
        "feature_key": "commands",
        "feature_name": "Commands",
        "description": "Command template support",
        "icon": "command",
        "sort_order": 2,
        "cli_types": ["claude-code", "codex", "gemini"],
    },
    {
        "id": "feature-hooks",
        "feature_key": "hooks",
        "feature_name": "Hooks",
        "description": "Hooks for automation workflows",
        "icon": "hook",
        "sort_order": 3,
        "cli_types": ["claude-code"],
    },
    {
        "id": "feature-agents-md",
        "feature_key": "agentsMd",
        "feature_name": "AGENTS.md",
        "description": "Agent instruction document support",
        "icon": "description",
        "sort_order": 4,
        "cli_types": ["claude-code", "codex", "gemini"],
    },
    {
        "id": "feature-agents",
        "feature_key": "agents",
        "feature_name": "Agents",
        "description": "Agent definitions and configuration",
        "icon": "agent",
        "sort_order": 5,
        "cli_types": ["claude-code"],
    },
    {
        "id": "feature-output-style",
        "feature_key": "outputStyle",
        "feature_name": "Output Style",
        "description": "Output style configuration",
        "icon": "style",
        "sort_order": 6,
        "cli_types": ["claude-code"],
    },
    {
        "id": "feature-skills",
        "feature_key": "skills",
        "feature_name": "Skills",
        "description": "Reusable skills and capability files",
        "icon": "sparkles",
        "sort_order": 7,
        "cli_types": ["claude-code", "codex", "gemini"],
    },
    {
        "id": "feature-scripts",
        "feature_key": "scripts",
        "feature_name": "Scripts",
        "description": "Executable scripts and helper files",
        "icon": "terminal",
        "sort_order": 8,
        "cli_types": ["claude-code", "codex", "gemini"],
    },
]


def should_create_default_workspace() -> bool:
    """依部署模式決定是否需要建立預設 workspace。"""
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
        port_mappings=[],
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
        port_mappings=[],
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
    """建立預設模型配置"""
    # 檢查是否已有模型配置
    existing_configs = db.query(ModelConfig).count()
    if existing_configs > 0:
        logger.info("模型配置已存在，跳過建立預設配置")
        return

    # Claude 模型配置
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
    logger.info("建立 4 個預設模型配置")


def create_default_workspace(db: Session) -> None:
    """建立預設 workspace (default-workspace)"""
    settings = get_settings()

    if not should_create_default_workspace():
        logger.info("目前設定未啟用預設 workspace bootstrap，跳過建立")
        return

    # 檢查是否已存在 default-workspace
    workspace_id = settings.BOOTSTRAP_DEFAULT_WORKSPACE_ID
    existing_workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if existing_workspace:
        if _reconcile_existing_docker_default_workspace(existing_workspace):
            logger.info(
                "Updated existing docker default workspace browser WebRTC contract: %s",
                existing_workspace.id,
            )
        else:
            logger.info("預設 workspace 已存在，跳過建立")
        return

    # 取得預設使用者
    default_user = _get_default_workspace_owner(db)
    if not default_user:
        logger.warning("找不到預設使用者，無法建立預設 workspace")
        return

    if settings.RUNTIME_PROVISIONER == "kubernetes":
        default_workspace = _create_kubernetes_default_workspace(default_user)
    else:
        default_workspace = _create_docker_default_workspace(default_user)

    db.add(default_workspace)
    logger.info("建立預設 workspace: %s", default_workspace.id)


def ensure_bootstrap_default_workspace(
    *,
    max_attempts: int = 5,
    retry_interval_seconds: float = 2.0,
) -> bool:
    """確保 bootstrap 預設 workspace 存在。

    Kubernetes 首次安裝時，workspace-manager 可能會早於 init SQL 建立 admin user。
    這裡用短暫重試來避免第一次啟動就永遠跳過 default workspace。
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
                logger.info("bootstrap 預設 workspace 已存在: %s", workspace_id)
                return True

            create_default_workspace(db)
            db.commit()

            existing_workspace = (
                db.query(Workspace).filter(Workspace.id == workspace_id).first()
            )
            if existing_workspace:
                logger.info(
                    "bootstrap 預設 workspace 已建立完成: %s (attempt %s/%s)",
                    workspace_id,
                    attempt,
                    max_attempts,
                )
                return True

            logger.info(
                "bootstrap 預設 workspace 尚未建立完成，稍後重試 (attempt %s/%s)",
                attempt,
                max_attempts,
            )
        except Exception:
            db.rollback()
            logger.exception(
                "bootstrap 預設 workspace 建立失敗 (attempt %s/%s)",
                attempt,
                max_attempts,
            )
        finally:
            db.close()

        if attempt < max_attempts:
            time.sleep(retry_interval_seconds)

    logger.warning("bootstrap 預設 workspace 建立重試完成但仍不存在: %s", workspace_id)
    return False


def create_default_template_categories(db: Session) -> None:
    """建立或更新預設模板分類"""
    existing_categories = {
        category.id: category
        for category in db.query(TemplateCategory).all()
    }
    active_default_ids = {category["id"] for category in DEFAULT_TEMPLATE_CATEGORIES}
    legacy_default_ids = {
        "general",
        "web",
        "frontend",
        "backend",
        "fullstack",
        "ai",
        "devops",
        "tooling",
        "automation",
        "documentation",
    }

    created_count = 0
    updated_count = 0

    for category_data in DEFAULT_TEMPLATE_CATEGORIES:
        existing = existing_categories.get(category_data["id"])
        if existing:
            changed = False
            if existing.name != category_data["name"]:
                existing.name = category_data["name"]
                changed = True
            if existing.description != category_data["description"]:
                existing.description = category_data["description"]
                changed = True
            if existing.icon != category_data["icon"]:
                existing.icon = category_data["icon"]
                changed = True
            if existing.sort_order != category_data["sort_order"]:
                existing.sort_order = category_data["sort_order"]
                changed = True
            if not existing.is_active:
                existing.is_active = True
                changed = True

            if changed:
                updated_count += 1
            continue

        db.add(
            TemplateCategory(
                id=category_data["id"],
                name=category_data["name"],
                description=category_data["description"],
                icon=category_data["icon"],
                sort_order=category_data["sort_order"],
                is_active=True,
            )
        )
        created_count += 1

    for category_id, category in existing_categories.items():
        if category_id in legacy_default_ids and category_id not in active_default_ids and category.is_active:
            category.is_active = False
            updated_count += 1

    logger.info("模板分類同步完成: 建立 %s 個，更新 %s 個", created_count, updated_count)


def create_default_template_features(db: Session) -> None:
    """建立或更新預設模板功能"""
    existing_features = {
        feature.feature_key: feature
        for feature in db.query(TemplateFeature).all()
    }
    existing_cli_links = {
        (row.feature_id, row.cli_type)
        for row in db.query(TemplateFeatureCliType).all()
    }
    active_default_keys = {feature["feature_key"] for feature in DEFAULT_TEMPLATE_FEATURES}
    legacy_default_keys = {
        "mcp",
        "commands",
        "hooks",
        "agentsMd",
        "agents",
        "outputStyle",
        "files",
        "skills",
        "scripts",
    }

    created_count = 0
    updated_count = 0
    cli_link_count = 0

    for feature_data in DEFAULT_TEMPLATE_FEATURES:
        existing = existing_features.get(feature_data["feature_key"])
        if existing:
            changed = False
            if existing.id != feature_data["id"]:
                existing.id = feature_data["id"]
                changed = True
            if existing.feature_name != feature_data["feature_name"]:
                existing.feature_name = feature_data["feature_name"]
                changed = True
            if existing.description != feature_data["description"]:
                existing.description = feature_data["description"]
                changed = True
            if existing.icon != feature_data["icon"]:
                existing.icon = feature_data["icon"]
                changed = True
            if existing.sort_order != feature_data["sort_order"]:
                existing.sort_order = feature_data["sort_order"]
                changed = True
            if not existing.is_active:
                existing.is_active = True
                changed = True

            feature_record = existing
            if changed:
                updated_count += 1
        else:
            feature_record = TemplateFeature(
                id=feature_data["id"],
                feature_key=feature_data["feature_key"],
                feature_name=feature_data["feature_name"],
                description=feature_data["description"],
                icon=feature_data["icon"],
                sort_order=feature_data["sort_order"],
                is_active=True,
            )
            db.add(feature_record)
            existing_features[feature_data["feature_key"]] = feature_record
            created_count += 1

        for cli_type in feature_data["cli_types"]:
            link_key = (feature_record.id, cli_type)
            if link_key in existing_cli_links:
                continue
            db.add(
                TemplateFeatureCliType(
                    feature_id=feature_record.id,
                    cli_type=cli_type,
                )
            )
            existing_cli_links.add(link_key)
            cli_link_count += 1

    for feature_key, feature in existing_features.items():
        if feature_key in legacy_default_keys and feature_key not in active_default_keys and feature.is_active:
            feature.is_active = False
            updated_count += 1

    logger.info(
        "模板功能同步完成: 建立 %s 個，更新 %s 個，新增 CLI 關聯 %s 個",
        created_count,
        updated_count,
        cli_link_count,
    )


def load_seed_data() -> None:
    """載入種子資料（使用者由 init SQL 建立，default workspace 僅限 Docker 模式）"""
    logger.info("開始載入種子資料...")

    db: Session = SessionLocal()
    try:
        # 建立預設模型配置
        create_default_model_configs(db)

        # 建立預設 workspace
        create_default_workspace(db)

        # 建立預設模板分類
        create_default_template_categories(db)

        # 建立預設模板功能
        create_default_template_features(db)

        # 提交變更
        db.commit()
        logger.info("✅ 種子資料載入完成")

    except Exception as e:
        logger.error(f"❌ 種子資料載入失敗: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    # 設定日誌
    logging.basicConfig(level=logging.INFO)
    load_seed_data()
