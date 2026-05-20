"""Workspace runtime provisioning service and strategy implementation"""

from __future__ import annotations

import logging
import random
import socket
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db import models as db_models
from app.services.script_template_engine import ScriptTemplateEngine
from app.services.orchestrator import (
    OrchestratorFactory,
    RuntimeContext,
    RuntimeInfo,
    VolumeMount,
    PortMapping,
    NetworkConfig,
    ResourceRequirements,
)
from app.services.knowledge_base_attachment_service import (
    KnowledgeBaseAttachmentService,
)
from app.utils.path_resolver import PathResolver

logger = logging.getLogger(__name__)

# Port allocation range
PORT_RANGE_MIN = 30000
PORT_RANGE_MAX = 60000

TEMPLATE_ROOT = Path(__file__).resolve().parent.parent / "jinja_templates" / "runtime"
CODEX_DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent / "defaults" / "codex" / "config.toml"
)

AGENT_STATE_MOUNTS = {
    "claude/home": "/home/developer/.claude",
    "codex/home": "/home/developer/.codex",
    "codex/sessions": "/home/developer/.codex-sessions",
    "gemini/home": "/home/developer/.gemini",
}


class RuntimeProvisionService:
    """Service responsible for scheduling workspace runtime provisioning."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.template_engine = ScriptTemplateEngine(TEMPLATE_ROOT)
        # Dynamically get settings to ensure correct configuration in test environment
        self.settings = get_settings()
        self.script_output_root = Path(self.settings.RUNTIME_SCRIPT_ROOT)

    def _get_reserved_browser_webrtc_udp_ranges(self) -> tuple[tuple[int, int], ...]:
        ranges: list[tuple[int, int]] = []
        for item in self.settings.BROWSER_WEBRTC_RESERVED_UDP_RANGES:
            if "-" not in item:
                logger.warning(
                    "Ignoring invalid browser WebRTC reserved UDP range: %s", item
                )
                continue
            start_text, end_text = item.split("-", 1)
            try:
                start = int(start_text.strip())
                end = int(end_text.strip())
            except ValueError:
                logger.warning(
                    "Ignoring invalid browser WebRTC reserved UDP range: %s", item
                )
                continue
            if start > end:
                logger.warning(
                    "Ignoring descending browser WebRTC reserved UDP range: %s", item
                )
                continue
            ranges.append((start, end))
        return tuple(ranges)

    def _is_reserved_browser_webrtc_udp_port(self, port: int) -> bool:
        return any(
            start <= port <= end
            for start, end in self._get_reserved_browser_webrtc_udp_ranges()
        )

    def _is_port_available(self, port: int, protocol: str) -> bool:
        socket_type = socket.SOCK_STREAM if protocol == "tcp" else socket.SOCK_DGRAM
        try:
            with socket.socket(socket.AF_INET, socket_type) as sock:
                sock.bind(("0.0.0.0", port))
                return True
        except OSError:
            return False

    def _find_available_browser_webrtc_port(
        self, exclude: set[int] | None = None
    ) -> int:
        exclude = exclude or set()

        for _ in range(100):
            port = random.randint(PORT_RANGE_MIN, PORT_RANGE_MAX)
            if port in exclude or self._is_reserved_browser_webrtc_udp_port(port):
                continue
            if self._is_port_available(port, "tcp") and self._is_port_available(
                port, "udp"
            ):
                return port

        raise RuntimeError(
            f"Could not allocate a browser WebRTC host port in range {PORT_RANGE_MIN}-{PORT_RANGE_MAX}"
        )

    def _resolve_browser_nat1to1_ip(self) -> str | None:
        if self.settings.RUNTIME_PROVISIONER != "docker":
            return None
        return os.environ.get("BROWSER_WEBRTC_NAT1TO1_IP", "127.0.0.1")

    # -- Background task main process --------------------------------------------------
    def execute_runtime_provision(self, workspace_id: str) -> None:
        workspace = self._get_workspace(workspace_id)
        if not workspace:
            logger.error("Workspace %s does not exist, cannot provision", workspace_id)
            return

        job = db_models.WorkspaceRuntimeJob(
            id=str(uuid4()),
            workspace_id=workspace.id,
            operation="provision",
            strategy=self.settings.RUNTIME_PROVISIONER,
            status="queued",
            retries=0,
            scheduled_at=datetime.utcnow(),
        )
        self.db.add(job)
        self.db.flush()

        self._log_event(
            workspace.id, "queued", "Queued runtime provision", {"jobId": job.id}
        )
        workspace.runtime_status = "starting"
        self.db.commit()

        try:
            self._perform_job(workspace, job)
        except Exception as exc:  # pragma: no cover - actual errors need logging
            logger.exception("Workspace %s provision failed", workspace.id)
            self.db.rollback()
            workspace = self._get_workspace(workspace_id)
            job = self._get_runtime_job(job.id)
            if not workspace or not job:
                logger.error(
                    "Cannot find workspace or job after rollback, cannot update failed status"
                )
                return
            self._handle_failure(workspace, job, exc)
        finally:
            self.db.commit()

    def _perform_job(
        self, workspace: db_models.Workspace, job: db_models.WorkspaceRuntimeJob
    ) -> None:
        job.status = "provisioning"
        job.started_at = datetime.utcnow()
        self._log_event(workspace.id, "provisioning", "BeginCreate Workspace Runtime")
        self.db.commit()

        # 1. Prepare runtime context
        context = self._build_runtime_context(workspace)

        self._log_event(
            workspace.id,
            "preparing",
            "Generated provision script and environment settings",
            {
                "environment": {
                    k: v for k, v in context.environment.items() if "KEY" not in k
                },  # Hide sensitive keys
                "ports": [p.__dict__ for p in context.ports],
            },
        )
        self.db.commit()

        # 2. Get Orchestrator
        orchestrator = OrchestratorFactory.get_orchestrator()

        # 3. Execute provisioning
        result = orchestrator.create_workspace_runtime(workspace, context)

        self._log_event(
            workspace.id,
            "provisioned",
            "Strategy execution completed, update runtime status",
            {"identifier": result.identifier},
        )

        # 4. Update Workspace Status
        self._update_workspace_runtime(workspace, result)

        # 5. Start Browser Container
        try:
            self._log_event(
                workspace.id, "browser_starting", "BeginCreate Browser Container"
            )
            browser_context = self._build_browser_runtime_context(workspace)
            browser_result = orchestrator.create_chrome_runtime(
                workspace, browser_context
            )
            self._update_browser_runtime(workspace, browser_result)
            self._log_event(
                workspace.id,
                "browser_ready",
                "Browser container is ready",
                {
                    "browser_identifier": browser_result.identifier,
                    "browser_webrtc_port": workspace.browser_webrtc_external_port,
                },
            )
        except Exception as exc:
            # Browser container startup failure should not affect main runtime
            logger.error(
                f"Workspace {workspace.id}: Browser ContainerStartFailed: {exc}",
                exc_info=True,
            )
            workspace.browser_status = "error"
            self._log_event(
                workspace.id,
                "browser_error",
                f"Browser ContainerStartFailed: {exc}",
            )

        # 6. Start Canvas Container
        try:
            self._log_event(
                workspace.id, "canvas_starting", "BeginCreate Canvas Container"
            )
            canvas_context = self._build_canvas_runtime_context(workspace)
            canvas_result = orchestrator.create_canvas_runtime(
                workspace, canvas_context
            )
            self._update_canvas_runtime(workspace, canvas_result)
            self._log_event(
                workspace.id,
                "canvas_ready",
                "Canvas container is ready",
                {
                    "canvas_identifier": canvas_result.identifier,
                    "canvas_port": workspace.canvas_external_port,
                },
            )
        except Exception as exc:
            # Canvas container startup failure should not affect main runtime
            logger.error(
                f"Workspace {workspace.id}: Canvas ContainerStartFailed: {exc}",
                exc_info=True,
            )
            workspace.canvas_status = "error"
            self._log_event(
                workspace.id,
                "canvas_error",
                f"Canvas ContainerStartFailed: {exc}",
            )

        job.status = "completed"
        job.finished_at = datetime.utcnow()
        self._log_event(workspace.id, "completed", "Workspace runtime is ready")

    def _build_runtime_context(self, workspace: db_models.Workspace) -> RuntimeContext:
        """Build runtime context"""

        # 0. Allocate fixed port (resolve port change issue after docker restart)
        self._allocate_ports_if_needed(workspace)

        # 1. Prepare script (startup script)
        workspace_dir = self.script_output_root / workspace.id
        environment = self._build_environment(workspace)

        # Port configuration (now using fixed allocated port)
        ports_config = self._build_ports_config(workspace)

        # Render startup.sh
        self.template_engine.render_to_file(
            "docker/startup.sh.j2",
            workspace_dir / "startup.sh",
            {
                "workspace": {"id": workspace.id, "name": workspace.name},
                "environment": environment,
                "ports": ports_config,  # Port configuration passed to template
                "git": {"url": workspace.git_url, "branch": workspace.branch},
            },
            executable=True,
        )

        # 2. Build volume mounts
        volumes = self._build_volumes(workspace)

        # 3. Build port mappings
        port_mappings = []
        for p in ports_config["mappings"]:
            port_mappings.append(
                PortMapping(
                    container_port=p["container_port"],
                    host_port=p["host_port"],
                    protocol=p["protocol"],
                )
            )

        # Add default port
        port_mappings.append(
            PortMapping(
                container_port=ports_config["default_internal_port"],
                host_port=workspace.runtime_external_port,  # If exists, use it
            )
        )
        # Note: Canvas render server (3003) moved to separate workspace-canvas container
        port_mappings.append(
            PortMapping(
                container_port=ports_config["terminal_internal_port"],
                host_port=workspace.terminal_external_port,
            )
        )

        # 4. Build network configuration
        network = NetworkConfig(
            network_name=self.settings.DOCKER_NETWORK, network_mode="bridge"
        )

        # 5. Get Image
        from app.services.container_image_service import get_container_image_service

        image_service = get_container_image_service()
        docker_image = image_service.get_docker_image_name(workspace.runtime)

        return RuntimeContext(
            environment=environment,
            volumes=volumes,
            ports=port_mappings,
            network=network,
            labels={
                "image": docker_image,
                "command": "/start_services.sh",
                "working_dir": "/workspace-runtime",
            },
        )

    def _build_environment(self, workspace: db_models.Workspace) -> dict[str, str]:
        # Browser container connection information (for service discovery)
        browser_container_name = f"workspace-browser-{workspace.id}"

        env = {
            "WORKSPACE_ID": workspace.id,
            "WORKSPACE_NAME": workspace.name,
            "WORKSPACE_RUNTIME_PORT": str(workspace.runtime_internal_port or 3002),
            "NODE_ENV": self.settings.ENV,
            "ENV": self.settings.ENV,
            "ALLOWED_ORIGINS": '["*"]',
            "DATABASE_URL": self.settings.DATABASE_URL,
            "REDIS_URL": self.settings.REDIS_URL,
            "MANAGER_URL": f"http://workspace-manager:{self.settings.PORT}",
            "INTERNAL_API_TOKEN": self.settings.INTERNAL_API_TOKEN,
            # Browser container connection information
            "BROWSER_CONTAINER_NAME": browser_container_name,
            "BROWSER_WEBRTC_INTERNAL_URL": workspace.browser_webrtc_internal_url
            or f"http://{browser_container_name}:6080",
            "BROWSER_CDP_URL": f"http://{browser_container_name}:9223",
            # Keycloak JWT authentication (workspace-runtime needs to verify access token from frontend)
            "KEYCLOAK_SERVER_URL": self.settings.KEYCLOAK_SERVER_URL,
            "KEYCLOAK_REALM": self.settings.KEYCLOAK_REALM,
            "KEYCLOAK_CLIENT_ID": self.settings.KEYCLOAK_CLIENT_ID,
            # Canvas container connection information (for service discovery)
            "CANVAS_CONTAINER_NAME": f"workspace-canvas-{workspace.id}",
            "CANVAS_INTERNAL_URL": workspace.canvas_internal_url
            or f"http://workspace-canvas-{workspace.id}:3003",
            "CANVAS_API_URL": f"http://workspace-canvas-{workspace.id}:3013",
        }

        if workspace.git_url:
            env["GIT_REPO_URL"] = workspace.git_url
            env["GIT_BRANCH"] = workspace.branch or "main"

        try:
            # Get workspace owner's user settings
            user_settings = self.db.scalar(
                select(db_models.UserSetting).where(
                    db_models.UserSetting.user_id == workspace.owner_id
                )
            )

            if user_settings:
                if user_settings.ssh_private_key:
                    env["SSH_PRIVATE_KEY"] = user_settings.ssh_private_key
                if user_settings.ssh_public_key:
                    env["SSH_PUBLIC_KEY"] = user_settings.ssh_public_key
                if user_settings.git_user_name:
                    env["GIT_USER_NAME"] = user_settings.git_user_name
                if user_settings.git_user_email:
                    env["GIT_USER_EMAIL"] = user_settings.git_user_email
        except Exception as e:
            logger.warning(f"Cannot get user settings: {e}")

        for item in workspace.env_vars or []:
            key = item.get("key")
            value = item.get("value")
            if key and value:
                env[key] = str(value)
        return env

    def _build_ports_config(self, workspace: db_models.Workspace) -> dict[str, Any]:
        """Build port configuration dictionary (for template rendering)"""
        default_port = workspace.runtime_internal_port or 3002
        canvas_port = workspace.canvas_internal_port or 3003
        terminal_port = 3004

        return {
            "default_internal_port": default_port,
            "canvas_internal_port": canvas_port,
            "terminal_internal_port": terminal_port,
            "mappings": [],
        }

    def _build_volumes(self, workspace: db_models.Workspace) -> list[VolumeMount]:
        safe_workspace_id = workspace.id.replace("-", "_")

        host_workspace = (
            self._resolve_host_mount_path(self.settings.HOST_WORKSPACES_DIR)
            / safe_workspace_id
        )
        host_scripts = (
            self._resolve_host_mount_path(self.settings.HOST_WORKSPACE_SCRIPTS_DIR)
            / safe_workspace_id
        )
        host_agent_state = self._agent_state_host_root(safe_workspace_id)
        host_marketplace_install = (
            self._resolve_host_mount_path(self.settings.HOST_MARKETPLACE_INSTALL_DIR)
            / safe_workspace_id
        )
        manager_workspace = (
            Path(self.settings.MANAGER_WORKSPACES_DIR) / safe_workspace_id
        )
        manager_scripts = (
            Path(self.settings.MANAGER_WORKSPACE_SCRIPTS_DIR) / safe_workspace_id
        )
        manager_agent_state = self._agent_state_manager_root(safe_workspace_id)
        manager_marketplace_install = (
            Path(self.settings.MANAGER_MARKETPLACE_INSTALL_DIR) / safe_workspace_id
        )
        manager_knowledge_bases = Path(self.settings.MANAGER_KNOWLEDGE_BASES_DIR)

        manager_workspace.mkdir(parents=True, exist_ok=True)
        manager_scripts.mkdir(parents=True, exist_ok=True)
        for provider_path in AGENT_STATE_MOUNTS:
            (manager_agent_state / provider_path).mkdir(parents=True, exist_ok=True)
        manager_marketplace_install.mkdir(parents=True, exist_ok=True)
        manager_knowledge_bases.mkdir(parents=True, exist_ok=True)
        self._write_codex_default_config(manager_agent_state)

        if workspace.setup_script:
            custom_setup_file = manager_scripts / "custom-setup.sh"
            custom_setup_file.write_text(workspace.setup_script, encoding="utf-8")
            custom_setup_file.chmod(0o755)

        volumes = [
            VolumeMount(source=str(host_workspace), target="/workspace"),
            VolumeMount(source=str(host_scripts), target="/scripts"),
            *self._agent_state_volume_mounts(host_agent_state),
            VolumeMount(source=str(host_marketplace_install), target="/marketplace-install"),
            # Docker socket
            VolumeMount(source="/var/run/docker.sock", target="/var/run/docker.sock"),
        ]

        # Development mode volumes
        node_env = os.environ.get("NODE_ENV", "production")
        if node_env.lower() in ["development", "dev"]:
            host_workspace_runtime_dir = os.environ.get("HOST_WORKSPACE_RUNTIME_DIR")
            if host_workspace_runtime_dir:
                host_workspace_runtime = self._resolve_host_mount_path(
                    host_workspace_runtime_dir
                )
                volumes.append(
                    VolumeMount(
                        source=str(host_workspace_runtime / "app"),
                        target="/workspace-runtime/app",
                    )
                )
                volumes.append(
                    VolumeMount(
                        source=str(host_workspace_runtime / "scripts"),
                        target="/workspace-runtime/scripts",
                    )
                )
                volumes.append(
                    VolumeMount(
                        source=str(host_workspace_runtime / "agent-defaults"),
                        target="/workspace-runtime/agent-defaults",
                    )
                )
                volumes.append(
                    VolumeMount(
                        source=str(host_workspace_runtime / "tests"),
                        target="/workspace-runtime/tests",
                    )
                )
                volumes.append(
                    VolumeMount(
                        source=str(host_workspace_runtime / "vendor"),
                        target="/workspace-runtime/vendor",
                    )
                )
                volumes.append(
                    VolumeMount(
                        source=str(host_workspace_runtime / "pyproject.toml"),
                        target="/workspace-runtime/pyproject.toml",
                    )
                )
                volumes.append(
                    VolumeMount(
                        source=str(host_workspace_runtime / "uv.lock"),
                        target="/workspace-runtime/uv.lock",
                    )
                )
                volumes.append(
                    VolumeMount(
                        source=str(host_workspace_runtime / "supervisord.conf"),
                        target="/workspace-runtime/supervisord.conf",
                    )
                )
                volumes.append(
                    VolumeMount(
                        source=str(host_workspace_runtime / "supervisord.dev.conf"),
                        target="/workspace-runtime/supervisord.dev.conf",
                    )
                )

                host_project_root = os.environ.get("HOST_PROJECT_ROOT")
                if host_project_root:
                    host_project_root_path = self._resolve_host_mount_path(
                        host_project_root
                    )
                    volumes.append(
                        VolumeMount(
                            source=str(host_project_root_path / "workspace-terminal"),
                            target="/workspace-terminal",
                        )
                    )

        raw_attachments = getattr(workspace, "knowledge_base_attachments", [])
        if isinstance(raw_attachments, list):
            host_kb_root = self._resolve_host_mount_path(
                self.settings.HOST_KNOWLEDGE_BASES_DIR
            )
            for attachment in raw_attachments:
                kb = getattr(attachment, "knowledge_base", None)
                kb_id = getattr(kb, "id", None) or getattr(attachment, "kb_id", None)
                mount_alias = getattr(attachment, "mount_alias", None)
                if not isinstance(kb_id, str) or not isinstance(mount_alias, str):
                    continue

                (manager_knowledge_bases / kb_id).mkdir(parents=True, exist_ok=True)
                volumes.append(
                    VolumeMount(
                        source=str(host_kb_root / kb_id),
                        target=f"/knowledge/{mount_alias}",
                        read_only=getattr(attachment, "mode", "rw") == "ro",
                    )
                )

        return volumes

    def _agent_state_host_root(self, safe_workspace_id: str) -> Path:
        return (
            self._resolve_host_mount_path(self.settings.HOST_AGENT_STATE_DIR)
            / safe_workspace_id
        )

    def _agent_state_manager_root(self, safe_workspace_id: str) -> Path:
        return Path(self.settings.MANAGER_AGENT_STATE_DIR) / safe_workspace_id

    def _agent_state_volume_mounts(self, host_agent_state: Path) -> list[VolumeMount]:
        return [
            VolumeMount(source=str(host_agent_state / provider_path), target=target)
            for provider_path, target in AGENT_STATE_MOUNTS.items()
        ]

    def _write_codex_default_config(self, manager_agent_state: Path) -> None:
        config_path = manager_agent_state / "codex" / "home" / "config.toml"
        if config_path.exists():
            return

        config_path.write_text(
            CODEX_DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        config_path.chmod(0o600)

    def _resolve_host_mount_path(self, value: str) -> Path:
        path = Path(value).expanduser()
        if path.is_absolute():
            return path

        host_project_root = Path(os.environ.get("HOST_PROJECT_ROOT", "")).expanduser()
        if not host_project_root.is_absolute():
            raise ValueError(
                "HOST_PROJECT_ROOT must be an absolute path when host mount paths are relative"
            )

        return host_project_root / path

    def _allocate_ports_if_needed(self, workspace: db_models.Workspace) -> None:
        """Allocate fixed port for workspace (if not yet allocated)"""
        allocated = []

        # Runtime port
        if not workspace.runtime_external_port:
            workspace.runtime_external_port = self._find_available_port()
            allocated.append(workspace.runtime_external_port)

        # Canvas render server port
        if not workspace.canvas_external_port:
            workspace.canvas_external_port = self._find_available_port(
                exclude={workspace.runtime_external_port}
            )
            allocated.append(workspace.canvas_external_port)

        # Terminal port
        if not workspace.terminal_external_port:
            workspace.terminal_external_port = self._find_available_port(
                exclude={
                    workspace.runtime_external_port,
                    workspace.canvas_external_port,
                }
            )
            allocated.append(workspace.terminal_external_port)

        # Browser WebRTC (neko) port
        if not workspace.browser_webrtc_external_port:
            workspace.browser_webrtc_external_port = (
                self._find_available_browser_webrtc_port(
                    exclude={
                        workspace.runtime_external_port,
                        workspace.canvas_external_port,
                        workspace.terminal_external_port,
                    }
                )
            )
            allocated.append(workspace.browser_webrtc_external_port)

        # Browser CDP port
        if not workspace.browser_cdp_external_port:
            workspace.browser_cdp_external_port = self._find_available_port(
                exclude={
                    workspace.runtime_external_port,
                    workspace.canvas_external_port,
                    workspace.terminal_external_port,
                    workspace.browser_webrtc_external_port,
                }
            )
            allocated.append(workspace.browser_cdp_external_port)

        # Collect allocated ports to avoid conflicts
        all_allocated = {
            workspace.runtime_external_port,
            workspace.canvas_external_port,
            workspace.terminal_external_port,
            workspace.browser_webrtc_external_port,
            workspace.browser_cdp_external_port,
        }

        # Canvas management API port
        if not workspace.canvas_api_external_port:
            workspace.canvas_api_external_port = self._find_available_port(
                exclude=all_allocated
            )
            allocated.append(workspace.canvas_api_external_port)

        # Update URL
        workspace.runtime_external_url = (
            f"http://localhost:{workspace.runtime_external_port}"
        )
        workspace.terminal_external_url = (
            f"http://localhost:{workspace.terminal_external_port}"
        )
        workspace.browser_webrtc_external_url = (
            f"http://localhost:{workspace.browser_webrtc_external_port}"
        )
        workspace.canvas_external_url = (
            f"http://localhost:{workspace.canvas_external_port}"
        )

        if allocated:
            logger.info(
                f"Workspace {workspace.id}: allocated fixed ports: runtime={workspace.runtime_external_port}, "
                f"canvas={workspace.canvas_external_port}, terminal={workspace.terminal_external_port}, "
                f"browser_webrtc={workspace.browser_webrtc_external_port}, browser_cdp={workspace.browser_cdp_external_port}, "
                f"canvas_api={workspace.canvas_api_external_port}"
            )
            self.db.flush()

    def _find_available_port(
        self, exclude: set[int] = None, protocol: str = "tcp"
    ) -> int:
        """Randomly find an available port"""
        exclude = exclude or set()
        socket_type = socket.SOCK_STREAM if protocol == "tcp" else socket.SOCK_DGRAM

        for _ in range(100):
            port = random.randint(PORT_RANGE_MIN, PORT_RANGE_MAX)
            if port in exclude:
                continue
            try:
                with socket.socket(socket.AF_INET, socket_type) as s:
                    s.bind(("0.0.0.0", port))
                    return port
            except OSError:
                continue

        raise RuntimeError(
            f"Cannot find available port in range {PORT_RANGE_MIN}-{PORT_RANGE_MAX}"
        )

    def _handle_failure(
        self,
        workspace: db_models.Workspace,
        job: db_models.WorkspaceRuntimeJob,
        exc: Exception,
    ) -> None:
        job.status = "failed"
        job.error_message = str(exc)
        job.finished_at = datetime.utcnow()
        workspace.runtime_status = "error"
        workspace.runtime_last_seen = datetime.utcnow()
        self._log_event(
            workspace.id,
            "failed",
            "Provision failed, please check error and retry",
            {"error": str(exc)},
        )

    # -- QueryInterface --------------------------------------------------------
    def get_runtime_logs(
        self,
        workspace_id: str,
        *,
        limit: int = 100,
        stage: Optional[str] = None,
    ) -> list[db_models.WorkspaceRuntimeLog]:
        stmt: Select[tuple[db_models.WorkspaceRuntimeLog]] = select(
            db_models.WorkspaceRuntimeLog
        ).where(db_models.WorkspaceRuntimeLog.workspace_id == workspace_id)
        if stage:
            stmt = stmt.where(db_models.WorkspaceRuntimeLog.stage == stage)
        stmt = stmt.order_by(db_models.WorkspaceRuntimeLog.created_at.desc()).limit(
            limit
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_latest_job(
        self, workspace_id: str
    ) -> Optional[db_models.WorkspaceRuntimeJob]:
        stmt = (
            select(db_models.WorkspaceRuntimeJob)
            .where(db_models.WorkspaceRuntimeJob.workspace_id == workspace_id)
            .order_by(db_models.WorkspaceRuntimeJob.scheduled_at.desc())
        )
        return self.db.execute(stmt).scalars().first()

    # -- Private helper methods ----------------------------------------------------
    def _get_workspace(self, workspace_id: str) -> Optional[db_models.Workspace]:
        return self.db.get(db_models.Workspace, workspace_id)

    def _get_runtime_job(self, job_id: str) -> Optional[db_models.WorkspaceRuntimeJob]:
        return self.db.get(db_models.WorkspaceRuntimeJob, job_id)

    def _log_event(
        self,
        workspace_id: str,
        stage: str,
        message: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        log_entry = db_models.WorkspaceRuntimeLog(
            id=str(uuid4()),
            workspace_id=workspace_id,
            stage=stage,
            message=message,
            metadata=metadata or {},
            created_at=datetime.utcnow(),
        )
        self.db.add(log_entry)
        logger.info("[workspace:%s][%s] %s", workspace_id, stage, message)

    def _update_workspace_runtime(
        self, workspace: db_models.Workspace, runtime_info: RuntimeInfo
    ) -> None:
        workspace.runtime_id = runtime_info.identifier
        workspace.runtime_internal_url = runtime_info.internal_url

        # Keep allocated fixed port, do not override with actual container port
        # This can avoid port change issue after container restart
        if not workspace.runtime_external_url:
            workspace.runtime_external_url = runtime_info.external_url

        # Extract port info from extra_info (only for verification, don't override allocated port)
        ports_mapping = runtime_info.extra_info.get("ports", {})

        # Only update if not already set
        # (This maintains port consistency)
        default_port = workspace.runtime_internal_port or 3002
        default_key = f"{default_port}/tcp"

        # Validate if container is using correct port
        if default_key in ports_mapping:
            actual_port = ports_mapping[default_key]
            if workspace.runtime_external_port != actual_port:
                logger.warning(
                    f"Workspace {workspace.id}: Container actual port ({actual_port}) "
                    f"does not match allocated fixed port ({workspace.runtime_external_port}). "
                    f"Use fixed port to maintain consistency."
                )

        # Terminal - only update if not yet allocated
        terminal_port = 3004
        term_key = f"{terminal_port}/tcp"
        if term_key in ports_mapping and not workspace.terminal_external_url:
            workspace.terminal_external_url = (
                f"http://localhost:{workspace.terminal_external_port}"
            )

        attachment_service = KnowledgeBaseAttachmentService(self.db)
        workspace.runtime_mounted_kb_signature = attachment_service.reconcile_on_start(
            workspace_id=workspace.id
        )
        workspace.runtime_status = "running"
        workspace.runtime_last_seen = datetime.utcnow()

    def _build_browser_runtime_context(
        self, workspace: db_models.Workspace
    ) -> RuntimeContext:
        """Build browser runtime context"""
        from app.services.container_image_service import get_container_image_service

        image_service = get_container_image_service()

        safe_workspace_id = workspace.id.replace("-", "_")
        host_workspace = Path(self.settings.HOST_WORKSPACES_DIR) / safe_workspace_id

        # Ensure workspace directory exists
        host_workspace.mkdir(parents=True, exist_ok=True)

        # Browser container name (for service discovery)
        browser_container_name = f"workspace-browser-{workspace.id}"

        # Allocate unique UDP port for WebRTC media
        udp_port = workspace.browser_webrtc_external_port

        # Port mappings for Browser (neko WebRTC + CDP + UDP media)
        port_mappings = [
            PortMapping(
                container_port=6080,
                host_port=workspace.browser_webrtc_external_port,
                protocol="tcp",
            ),  # neko WebRTC (HTTP + WS signaling)
            PortMapping(
                container_port=9223,
                host_port=workspace.browser_cdp_external_port,
                protocol="tcp",
            ),  # CDP proxy
            PortMapping(
                container_port=udp_port, host_port=udp_port, protocol="udp"
            ),  # WebRTC media (UDPMUX)
        ]

        # Browser container mounts the same workspace directory
        volumes = [
            VolumeMount(source=str(host_workspace), target="/workspace"),
        ]

        network = NetworkConfig(
            network_name=self.settings.DOCKER_NETWORK, network_mode="bridge"
        )

        return RuntimeContext(
            environment={
                "WORKSPACE_ID": workspace.id,
                "CONTAINER_NAME": browser_container_name,
                # neko Settings
                "NEKO_SERVER_BIND": ":6080",
                "NEKO_DESKTOP_SCREEN": "1440x900@30",
                "NEKO_MEMBER_MULTIUSER_USER_PASSWORD": "neko",
                "NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD": "admin",
                "NEKO_WEBRTC_ICELITE": "1",
                "NEKO_WEBRTC_UDPMUX": str(udp_port),
                "NEKO_WEBRTC_NAT1TO1": self._resolve_browser_nat1to1_ip(),
                "NEKO_SESSION_IMPLICIT_HOSTING": "true",
            },
            volumes=volumes,
            ports=port_mappings,
            network=network,
            labels={
                "image": image_service.get_browser_image_name(),
                "command": None,
                "working_dir": "/workspace",
            },
        )

    def _update_browser_runtime(
        self, workspace: db_models.Workspace, runtime_info: RuntimeInfo
    ) -> None:
        """Update Browser Runtime Status"""
        workspace.browser_container_id = runtime_info.identifier
        workspace.browser_webrtc_internal_url = runtime_info.internal_url
        workspace.browser_webrtc_external_url = runtime_info.external_url
        workspace.browser_status = "running"
        workspace.browser_last_seen = datetime.utcnow()

    def _build_canvas_runtime_context(
        self, workspace: db_models.Workspace
    ) -> RuntimeContext:
        """Build canvas runtime context"""
        from app.services.container_image_service import get_container_image_service

        image_service = get_container_image_service()

        safe_workspace_id = workspace.id.replace("-", "_")
        host_workspace = Path(self.settings.HOST_WORKSPACES_DIR) / safe_workspace_id

        # Ensure workspace directory exists
        host_workspace.mkdir(parents=True, exist_ok=True)

        canvas_container_name = f"workspace-canvas-{workspace.id}"

        # Port mappings: 3003 (render server) + 3013 (management API)
        port_mappings = [
            PortMapping(
                container_port=3003,
                host_port=workspace.canvas_external_port,
                protocol="tcp",
            ),
            PortMapping(
                container_port=3013,
                host_port=workspace.canvas_api_external_port,
                protocol="tcp",
            ),
        ]

        # Mount the same workspace directory
        volumes = [
            VolumeMount(source=str(host_workspace), target="/workspace"),
        ]

        network = NetworkConfig(
            network_name=self.settings.DOCKER_NETWORK, network_mode="bridge"
        )

        return RuntimeContext(
            environment={
                "WORKSPACE_ID": workspace.id,
                "CONTAINER_NAME": canvas_container_name,
                "PORT": "3003",
                "API_PORT": "3013",
                "WORKSPACE_DIR": "/workspace",
                "NODE_ENV": "development",
            },
            volumes=volumes,
            ports=port_mappings,
            network=network,
            labels={
                "image": image_service.get_canvas_image_name(),
                "command": None,
                "working_dir": "/workspace",
            },
        )

    def _update_canvas_runtime(
        self, workspace: db_models.Workspace, runtime_info: RuntimeInfo
    ) -> None:
        """Update Canvas Runtime Status"""
        workspace.canvas_container_id = runtime_info.identifier
        workspace.canvas_internal_url = runtime_info.internal_url
        workspace.canvas_external_url = (
            runtime_info.external_url
            or f"http://localhost:{workspace.canvas_external_port}"
        )
        workspace.canvas_status = "running"
        workspace.canvas_last_seen = datetime.utcnow()
        workspace.canvas_created_at = datetime.utcnow()


def run_runtime_provision_task(workspace_id: str) -> None:
    """Background task entry: Open new database connection and execute provisioning"""

    from app.db.database import SessionLocal  # Avoid circular import

    db = SessionLocal()
    try:
        service = RuntimeProvisionService(db)
        service.execute_runtime_provision(workspace_id)
    finally:
        db.close()


__all__ = [
    "RuntimeProvisionService",
    "run_runtime_provision_task",
]
